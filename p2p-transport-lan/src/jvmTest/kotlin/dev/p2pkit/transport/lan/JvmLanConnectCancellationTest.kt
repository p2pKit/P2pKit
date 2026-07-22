package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.TransportHint
import java.net.Socket
import java.net.SocketAddress
import java.util.concurrent.CountDownLatch
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertTrue

class JvmLanConnectCancellationTest {

    private class BlockingConnectSocket(
        private val entered: CompletableDeferred<Unit>,
        private val release: CountDownLatch
    ) : Socket() {
        override fun connect(endpoint: SocketAddress?, timeout: Int) {
            entered.complete(Unit)
            release.await()
        }
    }

    @Test
    fun cancellationAfterSocketConnectClosesUncommittedSocket() = runBlocking {
        val entered = CompletableDeferred<Unit>()
        val release = CountDownLatch(1)
        val socket = BlockingConnectSocket(entered, release)
        val registration = LanServiceRegistration(
            appId = AppId("connect-cancel-test"),
            localPeerId = PeerId("local-connect-cancel"),
            deviceName = "local",
            platform = Platform.JVM_DESKTOP
        )
        val transport = JvmLanDataTransport(registration, socketFactory = { socket })
        val peer = InternalPeer(
            publicPeer = Peer(
                id = PeerId("remote-connect-cancel"),
                name = "remote",
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            ),
            transportHints = listOf(
                TransportHint(TransportKind.LAN, host = "127.0.0.1", port = 9)
            )
        )

        val connectJob = launch { transport.connect(peer) }
        withTimeout(TEST_TIMEOUT_MILLIS) { entered.await() }
        connectJob.cancel()
        release.countDown()
        withTimeout(TEST_TIMEOUT_MILLIS) { connectJob.cancelAndJoin() }

        assertTrue(socket.isClosed, "cancelled connect must close the uncommitted socket")
    }

    private companion object {
        const val TEST_TIMEOUT_MILLIS: Long = 5_000
    }
}
