package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.PeerEvent
import javax.jmdns.ServiceInfo
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals

/** End-to-end ownership checks around the JVM discovery callback seam. */
class JvmDiscoveryRelayIntegrationTest {
    @Test
    fun lateCollectionStopAndRestartConvergeWithoutAReplayGap() = runBlocking {
        val suffix = System.nanoTime().toString()
        val appId = AppId("relay-$suffix")
        val localId = PeerId("local-$suffix")
        val remoteId = PeerId("remote-$suffix")
        val backend = JvmDeterministicDiscoveryTestBackend()
        val registration = LanServiceRegistration(
            appId = appId,
            localPeerId = localId,
            deviceName = "Observer",
            platform = Platform.JVM_DESKTOP,
            tcpPort = 45_000
        )
        val transport = JvmLanDiscoveryTransport(registration, backend)
        val service = ServiceInfo.create(
            registration.serviceTypeJmdns,
            remoteId.value,
            45_001,
            /* weight = */ 0,
            /* priority = */ 0,
            buildLanTxtProperties(
                peerId = remoteId,
                appId = appId,
                deviceName = "Remote",
                platform = Platform.ANDROID,
                supportedTransports = setOf(TransportKind.LAN),
                protocolVersion = registration.protocolVersion,
                fingerprint = null
            )
        )

        try {
            transport.startDiscovery()
            backend.advertise(
                JvmTestDiscoveryAdvertisement(
                    instanceName = remoteId.value,
                    info = service
                )
            )

            // Subscribe only after the callback. The old replay-zero flow
            // lost this Found; the state-backed relay must expose it.
            val sequence = async(start = CoroutineStart.UNDISPATCHED) {
                withTimeout(5_000) { transport.events.take(3).toList() }
            }
            transport.stopDiscovery()
            transport.startDiscovery()

            val events = sequence.await()
            assertEquals(
                listOf(
                    remoteId,
                    remoteId,
                    remoteId
                ),
                events.map(::peerIdOf)
            )
            assertEquals(
                listOf(
                    PeerEvent.Found::class,
                    PeerEvent.Lost::class,
                    PeerEvent.Found::class
                ),
                events.map { it::class }
            )
        } finally {
            backend.withdraw(remoteId.value)
            runCatching { transport.stopDiscovery() }
        }
    }

    private fun peerIdOf(event: PeerEvent): PeerId = when (event) {
        is PeerEvent.Found -> event.peer.publicPeer.id
        is PeerEvent.Updated -> event.peer.publicPeer.id
        is PeerEvent.Lost -> event.peerId
    }
}
