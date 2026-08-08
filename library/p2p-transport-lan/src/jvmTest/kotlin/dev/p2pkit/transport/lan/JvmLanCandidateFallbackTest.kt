package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.TransportHint
import java.net.ConnectException
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketAddress
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class JvmLanCandidateFallbackTest {

    private class RecordingSocket(private val failure: Exception? = null) : Socket() {
        val attempts = mutableListOf<InetSocketAddress>()

        override fun connect(endpoint: SocketAddress?, timeout: Int) {
            attempts += endpoint as InetSocketAddress
            failure?.let { throw it }
        }
    }

    @Test
    fun failedFirstCandidateIsClosedAndSecondCandidateConnects() = runBlocking {
        val first = RecordingSocket(ConnectException("injected refusal"))
        val second = RecordingSocket()
        val sockets = ArrayDeque(listOf(first, second))
        val transport = JvmLanDataTransport(registration(), socketFactory = { sockets.removeFirst() })

        val raw = transport.connect(peerWithHosts("192.168.1.20", "192.168.1.21"))
        try {
            assertEquals("192.168.1.20", first.attempts.single().hostString)
            assertEquals("192.168.1.21", second.attempts.single().hostString)
            assertTrue(first.isClosed, "a failed candidate socket must be closed before fallback")
        } finally {
            raw.close()
        }
    }

    private fun registration() = LanServiceRegistration(
        appId = AppId("candidate-fallback"),
        localPeerId = PeerId("candidate-local"),
        deviceName = "local",
        platform = Platform.JVM_DESKTOP
    )

    private fun peerWithHosts(vararg hosts: String) = InternalPeer(
        publicPeer = Peer(
            id = PeerId("candidate-remote"),
            name = "remote",
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = hosts.map { host ->
            TransportHint(TransportKind.LAN, host = host, port = 9_001)
        }
    )
}
