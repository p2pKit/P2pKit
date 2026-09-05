package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue

class JvmLanServiceInfoTest {
    private val peer = LocalPeerInfo(
        peerId = PeerId("service-info-test"),
        deviceName = "service-info-test",
        platform = Platform.JVM_DESKTOP,
        appId = AppId("dev.p2pkit.service-info-test"),
        supportedTransports = setOf(TransportKind.LAN)
    )

    private fun registration(
        port: Int = 0,
        profile: TransportSecurityProfile = TransportSecurityProfile.LegacyPlaintextV1
    ) = LanServiceRegistration(
        appId = peer.appId,
        localPeerId = peer.peerId,
        deviceName = peer.deviceName,
        platform = peer.platform,
        securityProfile = profile,
        fingerprint = if (profile == TransportSecurityProfile.AuthenticatedV2) {
            PeerFingerprint("p2f1-" + "a".repeat(52))
        } else {
            null
        },
        tcpPort = port
    )

    @Test
    fun serviceInfoRejectsUnboundAndOutOfRangeListenerPorts() {
        for (profile in TransportSecurityProfile.entries) {
            for (port in listOf(0, -1, 65_536)) {
                val failure = assertFailsWith<P2pError.TransportStartFailed> {
                    buildJmdnsServiceInfo(registration(port, profile), peer)
                }
                assertEquals(TransportKind.LAN, failure.transportKind)
            }
        }
    }

    @Test
    fun serviceInfoKeepsItsValidPortSnapshotAndWireProfile() {
        for (profile in TransportSecurityProfile.entries) {
            for (port in listOf(1, 42_000, 65_535)) {
                val registration = registration(port, profile)
                val info = buildJmdnsServiceInfo(registration, peer)
                registration.tcpPort = 0

                assertEquals(port, info.port)
                assertEquals(registration.serviceTypeJmdns, info.type)
                assertEquals(
                    registration.protocolVersion.toString(),
                    info.getPropertyString(LanConstants.TXT_PROTOCOL_VERSION)
                )
                assertEquals(registration.fingerprint?.value, info.getPropertyString(LanConstants.TXT_FINGERPRINT))
            }
        }
    }

    @Test
    fun advertisementMatchesListenerAfterStopAndRestart() = runBlocking {
        val registration = registration()
        val data = JvmLanDataTransport(registration)
        try {
            data.start().getOrThrow()
            val first = buildJmdnsServiceInfo(registration, peer)
            assertTrue(first.port in 1..65_535)
            assertEquals(data.tcpPort.value, first.port)

            data.stop()
            assertNull(data.tcpPort.value)
            assertEquals(0, registration.tcpPort, "detachment must keep its zero-port contract")
            assertFailsWith<P2pError.TransportStartFailed> { buildJmdnsServiceInfo(registration, peer) }

            data.start().getOrThrow()
            val restored = buildJmdnsServiceInfo(registration, peer)
            assertEquals(first.port, restored.port, "normal listener restart preserves the last live port")
            assertEquals(data.tcpPort.value, restored.port)
        } finally {
            data.close()
        }
    }
}
