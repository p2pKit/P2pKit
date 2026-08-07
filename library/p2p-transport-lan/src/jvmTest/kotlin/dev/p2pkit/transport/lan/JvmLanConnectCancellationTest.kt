package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.TransportHint
import java.io.IOException
import java.net.Socket
import java.net.SocketAddress
import java.util.concurrent.CountDownLatch
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

class JvmLanConnectCancellationTest {

    private open class BlockingConnectSocket(
        private val entered: CompletableDeferred<Unit>,
        private val release: CountDownLatch
    ) : Socket() {
        override fun connect(endpoint: SocketAddress?, timeout: Int) {
            entered.complete(Unit)
            release.await()
        }
    }

    private class FailOnceCloseSocket(
        entered: CompletableDeferred<Unit>,
        release: CountDownLatch
    ) : BlockingConnectSocket(entered, release) {
        private var closeAttempts = 0

        override fun close() {
            closeAttempts += 1
            if (closeAttempts == 1) throw IOException("injected close failure")
            super.close()
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

    @Test
    fun transportStopClosesPendingDialAndPreventsLateSuccess() = runBlocking<Unit> {
        val entered = CompletableDeferred<Unit>()
        val release = CountDownLatch(1)
        val socket = BlockingConnectSocket(entered, release)
        val transport = JvmLanDataTransport(
            LanServiceRegistration(
                appId = AppId("connect-stop-test"),
                localPeerId = PeerId("local-connect-stop"),
                deviceName = "local",
                platform = Platform.JVM_DESKTOP
            ),
            socketFactory = { socket }
        )
        val result = async { runCatching { transport.connect(testPeer("remote-connect-stop")) } }

        withTimeout(TEST_TIMEOUT_MILLIS) { entered.await() }
        transport.stop()
        assertTrue(socket.isClosed, "restartable stop must close every pending dial socket")
        release.countDown()

        assertIs<P2pError.ConnectionFailed>(
            withTimeout(TEST_TIMEOUT_MILLIS) { result.await() }.exceptionOrNull()
        )
        transport.close()
    }

    @Test
    fun failedPendingDialCleanupBlocksRestartUntilStopRetrySucceeds() = runBlocking<Unit> {
        val entered = CompletableDeferred<Unit>()
        val release = CountDownLatch(1)
        val socket = FailOnceCloseSocket(entered, release)
        val transport = JvmLanDataTransport(
            LanServiceRegistration(
                appId = AppId("connect-cleanup-retry"),
                localPeerId = PeerId("local-cleanup-retry"),
                deviceName = "local",
                platform = Platform.JVM_DESKTOP
            ),
            socketFactory = { socket }
        )
        val result = async { runCatching { transport.connect(testPeer("remote-cleanup-retry")) } }

        withTimeout(TEST_TIMEOUT_MILLIS) { entered.await() }
        assertFailsWith<IllegalStateException> { transport.stop() }
        assertFalse(
            transport.start().isSuccess,
            "restart must fail while failed cleanup ownership is retained"
        )

        transport.stop()
        release.countDown()
        assertIs<P2pError.ConnectionFailed>(
            withTimeout(TEST_TIMEOUT_MILLIS) { result.await() }.exceptionOrNull()
        )
        assertTrue(transport.start().isSuccess, "restart may proceed after cleanup retry succeeds")
        transport.close()
    }

    private fun testPeer(id: String) = InternalPeer(
        publicPeer = Peer(
            id = PeerId(id),
            name = "remote",
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = listOf(
            TransportHint(TransportKind.LAN, host = "127.0.0.1", port = 9)
        )
    )

    private companion object {
        const val TEST_TIMEOUT_MILLIS: Long = 5_000
    }
}
