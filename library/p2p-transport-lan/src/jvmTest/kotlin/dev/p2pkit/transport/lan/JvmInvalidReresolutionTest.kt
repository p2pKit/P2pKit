package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.PeerEvent
import java.net.InetAddress
import javax.jmdns.ServiceInfo
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNull

class JvmInvalidReresolutionTest {
    @Test
    fun latestInvalidResolutionWithdrawsPeerAndValidRecoveryFindsItAgain() = runBlocking {
        val suffix = System.nanoTime().toString()
        val appId = AppId("invalid-reresolution-$suffix")
        val localId = PeerId("local-$suffix")
        val remoteId = PeerId("remote-$suffix")
        val backend = JvmDeterministicDiscoveryTestBackend()
        val registration = LanServiceRegistration(
            appId = appId,
            localPeerId = localId,
            deviceName = "Observer",
            platform = Platform.JVM_DESKTOP,
            tcpPort = VALID_PORT
        )
        val transport = JvmLanDiscoveryTransport(registration, backend)
        val events = Channel<PeerEvent>(Channel.UNLIMITED)
        val collector = launch(start = CoroutineStart.UNDISPATCHED) {
            transport.events.collect(events::send)
        }
        val valid = service(remoteId.value, remoteId.value, appId.value, VALID_PORT)

        try {
            transport.startDiscovery()
            advertise(backend, remoteId.value, valid)
            assertFound(events.receiveNext(), remoteId)

            val invalidResolutions = listOf(
                JvmTestDiscoveryAdvertisement(
                    instanceName = remoteId.value,
                    info = service(remoteId.value, " ", appId.value, VALID_PORT)
                ),
                JvmTestDiscoveryAdvertisement(
                    instanceName = remoteId.value,
                    info = service(remoteId.value, remoteId.value, "${appId.value}-other", VALID_PORT)
                ),
                JvmTestDiscoveryAdvertisement(
                    instanceName = remoteId.value,
                    info = service("different-instance-$suffix", remoteId.value, appId.value, VALID_PORT)
                ),
                JvmTestDiscoveryAdvertisement(
                    instanceName = remoteId.value,
                    info = valid,
                    candidates = emptyList()
                ),
                JvmTestDiscoveryAdvertisement(
                    instanceName = remoteId.value,
                    info = service(remoteId.value, remoteId.value, appId.value, 0)
                )
            )

            invalidResolutions.forEachIndexed { index, invalid ->
                backend.advertise(invalid)
                assertEquals(remoteId, assertIs<PeerEvent.Lost>(events.receiveNext()).peerId)

                if (index == 0) {
                    assertNull(
                        withTimeoutOrNull(NO_EVENT_MILLIS) { transport.events.first() },
                        "a late collector must not receive an invalidated peer"
                    )
                }

                advertise(backend, remoteId.value, valid)
                assertFound(events.receiveNext(), remoteId)
            }
        } finally {
            backend.withdraw(remoteId.value)
            runCatching { transport.stopDiscovery() }
            collector.cancel()
            events.close()
        }
    }

    private fun service(instanceName: String, peerId: String, appId: String, port: Int): ServiceInfo =
        ServiceInfo.create(
            LanConstants.LEGACY_SERVICE_TYPE_JMDNS,
            instanceName,
            port,
            /* weight = */ 0,
            /* priority = */ 0,
            mapOf(
                LanConstants.TXT_PEER_ID to peerId,
                LanConstants.TXT_APP_ID to appId,
                LanConstants.TXT_DEVICE_NAME to "Remote",
                LanConstants.TXT_PLATFORM to Platform.ANDROID.name,
                LanConstants.TXT_CAPABILITIES to TransportKind.LAN.name,
                LanConstants.TXT_PROTOCOL_VERSION to LanConstants.LEGACY_PROTOCOL_VERSION.toString()
            )
        )

    private fun advertise(
        backend: JvmDeterministicDiscoveryTestBackend,
        instanceName: String,
        info: ServiceInfo
    ) {
        backend.advertise(
            JvmTestDiscoveryAdvertisement(
                instanceName = instanceName,
                info = info,
                candidates = listOf(InetAddress.getLoopbackAddress())
            )
        )
    }

    private suspend fun Channel<PeerEvent>.receiveNext(): PeerEvent =
        withTimeout(EVENT_TIMEOUT_MILLIS) { receive() }

    private fun assertFound(event: PeerEvent, expected: PeerId) {
        assertEquals(expected, assertIs<PeerEvent.Found>(event).peer.publicPeer.id)
    }

    private companion object {
        const val VALID_PORT: Int = 45_001
        const val EVENT_TIMEOUT_MILLIS: Long = 5_000
        const val NO_EVENT_MILLIS: Long = 200
    }
}
