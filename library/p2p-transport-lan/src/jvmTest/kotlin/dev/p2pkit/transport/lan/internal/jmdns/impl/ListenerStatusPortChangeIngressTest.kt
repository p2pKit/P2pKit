package dev.p2pkit.transport.lan.internal.jmdns.impl

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportSecurityProfile
import dev.p2pkit.transport.lan.JvmDeterministicDiscoveryTestBackend
import dev.p2pkit.transport.lan.JvmLanDiscoveryTransport
import dev.p2pkit.transport.lan.JvmTestDiscoveryAdvertisement
import dev.p2pkit.transport.lan.LanConstants
import dev.p2pkit.transport.lan.LanServiceRegistration
import dev.p2pkit.transport.lan.LanTxtRecordFixtures
import dev.p2pkit.transport.lan.internal.jmdns.JmDNS
import dev.p2pkit.transport.lan.internal.jmdns.ServiceEvent
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo
import dev.p2pkit.transport.lan.internal.jmdns.ServiceListener
import dev.p2pkit.transport.lan.internal.jmdns.impl.constants.DNSRecordClass
import dev.p2pkit.transport.lan.lanEndpoints
import java.net.Inet4Address
import java.net.Inet6Address
import java.net.InetAddress
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNotSame
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Real SRV field update and listener deduplication joined to the real Kotlin endpoint consumer. */
@OptIn(ExperimentalCoroutinesApi::class)
class ListenerStatusPortChangeIngressTest {
    @Test
    fun secureResolvedPortChangesReachPeerHintsWithoutDisablingDeduplication() =
        portChanges(TransportSecurityProfile.AuthenticatedV2, seedWithAdded = false)

    @Test
    fun legacyResolvedPortChangesReachPeerHintsWithoutDisablingDeduplication() =
        portChanges(TransportSecurityProfile.LegacyPlaintextV1, seedWithAdded = false)

    @Test
    fun secureCompleteAddedRecordSeedsPortComparison() =
        portChanges(TransportSecurityProfile.AuthenticatedV2, seedWithAdded = true)

    @Test
    fun legacyCompleteAddedRecordSeedsPortComparison() =
        portChanges(TransportSecurityProfile.LegacyPlaintextV1, seedWithAdded = true)

    private fun portChanges(profile: TransportSecurityProfile, seedWithAdded: Boolean) = runTest {
        val first = completeInfo(profile)
        val changed = changedPort(first, PORT_B)
        val restored = changedPort(changed, PORT_A)
        val hosts = first.inetAddresses.map { it.hostAddress }
        val fixture = DiscoveryFixture(profile)
        val collector = launch(start = CoroutineStart.UNDISPATCHED) {
            fixture.transport.events.collect(fixture.events::add)
        }
        try {
            fixture.transport.startDiscovery()
            if (seedWithAdded) {
                fixture.listener.serviceAdded(event(first.clone()))
            } else {
                fixture.listener.serviceResolved(event(first.clone()))
            }
            runCurrent()
            fixture.assertObservations(listOf(PORT_A), hosts)

            // A distinct unchanged record must not produce a second raw callback.
            fixture.listener.serviceResolved(event(first.clone()))
            runCurrent()
            fixture.assertObservations(listOf(PORT_A), hosts)

            fixture.listener.serviceResolved(event(changed.clone()))
            runCurrent()
            fixture.assertObservations(listOf(PORT_A, PORT_B), hosts)

            fixture.listener.serviceResolved(event(changed.clone()))
            runCurrent()
            fixture.assertObservations(listOf(PORT_A, PORT_B), hosts)

            fixture.listener.serviceResolved(event(restored.clone()))
            runCurrent()
            fixture.assertObservations(listOf(PORT_A, PORT_B, PORT_A), hosts)
            assertEquals(if (seedWithAdded) 1 else 0, fixture.added)
            assertEquals(0, fixture.removed)
        } finally {
            try {
                fixture.transport.stopDiscovery()
            } finally {
                collector.cancelAndJoin()
            }
        }
    }

    private fun completeInfo(profile: TransportSecurityProfile): ServiceInfoImpl = ServiceInfoImpl(
        LanConstants.serviceTypeJmdns(profile),
        "remote",
        "",
        PORT_A,
        0,
        0,
        true,
        LanTxtRecordFixtures.encode(LanTxtRecordFixtures.properties(profile).toList())
    ).apply {
        setServer("remote.local.")
        addAddress(InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1)) as Inet4Address)
        addAddress(InetAddress.getByAddress(ByteArray(16).also { it[15] = 1 }) as Inet6Address)
        assertTrue(hasData())
        assertNull(dns)
    }

    private fun changedPort(previous: ServiceInfoImpl, port: Int): ServiceInfoImpl = previous.clone().also { next ->
        assertNotSame(previous, next)
        assertNull(next.dns)
        val srv = DNSRecord.Service(
            next.qualifiedName,
            DNSRecordClass.CLASS_IN,
            true,
            120,
            next.priority,
            next.weight,
            port,
            next.server
        )
        assertFalse(srv.isExpired(srv.created))
        // Detached info: exercise the actual nonexpired SRV update, then forward its snapshot below.
        // This does not simulate JmDNSImpl cache/executor dispatch or a live multicast packet.
        next.updateRecord(DNSCache(1), srv.created, srv)
        assertEquals(port, next.port)
        assertTrue(next.hasData())
        assertEquals(previous, next, "ServiceInfo equality alone is only qualified-name equality")
        assertEquals(previous.type, next.type)
        assertEquals(previous.name, next.name)
        assertEquals(previous.server, next.server)
        assertEquals(previous.weight, next.weight)
        assertEquals(previous.priority, next.priority)
        assertEquals(previous.isPersistent, next.isPersistent)
        assertContentEquals(previous.textBytes, next.textBytes)
        assertContentEquals(previous.inetAddresses, next.inetAddresses)
        assertTrue(next.hasSameAddresses(previous))
    }

    private fun event(info: ServiceInfo): ServiceEvent = object : ServiceEvent(Any()) {
        override fun getDNS(): JmDNS = error("The detached listener regression must not create a live DNS handle")
        override fun getType(): String = info.type
        override fun getName(): String = info.name
        override fun getInfo(): ServiceInfo = info
    }

    private class DiscoveryFixture(private val profile: TransportSecurityProfile) {
        val backend = JvmDeterministicDiscoveryTestBackend()
        val events = mutableListOf<PeerEvent>()
        val rawPorts = mutableListOf<Int>()
        var added = 0
        var removed = 0
        val transport = JvmLanDiscoveryTransport(
            LanServiceRegistration(
                appId = AppId("lan-txt-test"),
                localPeerId = PeerId("local"),
                deviceName = "Observer",
                platform = Platform.JVM_DESKTOP,
                securityProfile = profile,
                fingerprint = if (profile == TransportSecurityProfile.AuthenticatedV2) {
                    PeerFingerprint("p2f1-" + "b".repeat(51) + "a")
                } else {
                    null
                },
                tcpPort = 45_000
            ),
            backend
        )
        val listener = ListenerStatus.ServiceListenerStatus(
            object : ServiceListener {
                override fun serviceAdded(event: ServiceEvent) {
                    added++
                }

                override fun serviceRemoved(event: ServiceEvent) {
                    removed++
                    backend.withdraw(event.name)
                }

                override fun serviceResolved(event: ServiceEvent) {
                    // Only real wrapper delivery reaches the existing backend/production Kotlin consumer.
                    rawPorts += event.info.port
                    backend.advertise(
                        JvmTestDiscoveryAdvertisement(event.name, event.info, event.info.inetAddresses.toList())
                    )
                }
            },
            ListenerStatus.SYNCHRONOUS
        )

        fun assertObservations(ports: List<Int>, hosts: List<String>) {
            // The Kotlin relay also deduplicates peers: peer events alone could falsely pass if the
            // native comparator were disabled. Require the exact raw callback sequence as well.
            assertEquals(ports, rawPorts, "Only changed ports may pass the real listener wrapper")
            assertEquals(ports.size, events.size)
            val first = assertIs<PeerEvent.Found>(events.first()).peer
            assertEquals(PeerId("remote"), first.publicPeer.id)
            assertEquals("Remote", first.publicPeer.name)
            if (profile == TransportSecurityProfile.AuthenticatedV2) {
                assertNotNull(first.authenticationHint)
            } else {
                assertNull(first.authenticationHint)
            }
            events.forEachIndexed { index, event ->
                val peer = if (index == 0) {
                    assertIs<PeerEvent.Found>(event).peer
                } else {
                    assertIs<PeerEvent.Updated>(event).peer
                }
                assertEquals(first.publicPeer, peer.publicPeer)
                assertEquals(first.origin, peer.origin)
                assertEquals(first.authenticationHint, peer.authenticationHint)
                val endpoints = peer.lanEndpoints()
                assertEquals(hosts, endpoints.map { it.host })
                assertEquals(List(hosts.size) { ports[index] }, endpoints.map { it.port })
            }
        }
    }

    private companion object {
        const val PORT_A = 45_001
        const val PORT_B = 45_002
    }
}
