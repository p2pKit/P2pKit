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
import java.net.BindException
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketAddress
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Deterministic ownership races at the JVM listener/dial lifecycle boundary. */
class JvmLanDataTransportOwnershipTest {

    private open class TrackingServerSocket : ServerSocket() {
        val bound = CountDownLatch(1)

        override fun bind(endpoint: SocketAddress?) {
            super.bind(endpoint)
            bound.countDown()
        }
    }

    private class GatedBindServerSocket(
        private val entered: CountDownLatch,
        private val release: CountDownLatch
    ) : TrackingServerSocket() {
        override fun bind(endpoint: SocketAddress?) {
            entered.countDown()
            awaitIgnoringInterrupt(release)
            super.bind(endpoint)
        }
    }

    private class SignallingAcceptServerSocket(
        private val acceptEntered: CountDownLatch
    ) : TrackingServerSocket() {
        override fun accept(): Socket {
            acceptEntered.countDown()
            return super.accept()
        }
    }

    private class FailOnceCloseServerSocket : TrackingServerSocket() {
        private val attempts = AtomicInteger()

        override fun close() {
            if (attempts.getAndIncrement() == 0) throw IOException("injected listener close failure")
            super.close()
        }
    }

    private class FailBindAndFirstCloseServerSocket : TrackingServerSocket() {
        private val closeAttempts = AtomicInteger()
        val closeAttemptCount: Int get() = closeAttempts.get()

        override fun bind(endpoint: SocketAddress?) {
            throw BindException("injected bind failure")
        }

        override fun close() {
            if (closeAttempts.getAndIncrement() == 0) throw IOException("injected bind cleanup failure")
            super.close()
        }
    }

    private class ImmediateConnectSocket : Socket() {
        override fun connect(endpoint: SocketAddress?, timeout: Int) = Unit
    }

    @Test
    fun cancellationWhileBindCompletesClosesTheUnpublishedListener() = runBlocking {
        val bindEntered = CountDownLatch(1)
        val releaseBind = CountDownLatch(1)
        val socket = GatedBindServerSocket(bindEntered, releaseBind)
        val registration = registration("cancelled-bind")
        val transport = JvmLanDataTransport(
            registration = registration,
            serverSocketFactory = { socket }
        )

        val starter = launch(Dispatchers.Default) { transport.start().getOrThrow() }
        await(bindEntered, "listener bind entry")
        starter.cancel()
        releaseBind.countDown()
        withTimeout(TEST_TIMEOUT_MS) { starter.join() }

        assertTrue(starter.isCancelled)
        assertTrue(socket.isClosed, "a bound result discarded by cancellation must be closed")
        assertNull(transport.tcpPort.value)
        assertEquals(0, registration.tcpPort)
        transport.stop()
    }

    @Test
    fun stopAtFinalDialHandoffCannotReturnAClosedRawConnection() = runBlocking {
        val handoffEntered = CountDownLatch(1)
        val releaseHandoff = CountDownLatch(1)
        val socket = ImmediateConnectSocket()
        val transport = JvmLanDataTransport(
            registration = registration("dial-handoff"),
            socketFactory = { socket },
            beforeDialOwnershipHandoffForTest = {
                handoffEntered.countDown()
                awaitIgnoringInterrupt(releaseHandoff)
            }
        )

        val result = async(Dispatchers.Default) {
            runCatching { transport.connect(peer("dial-handoff-peer")) }
        }
        await(handoffEntered, "final dial ownership handoff")
        transport.stop()
        releaseHandoff.countDown()

        val failure = withTimeout(TEST_TIMEOUT_MS) { result.await() }.exceptionOrNull()
        assertIs<P2pError.ConnectionFailed>(failure)
        assertTrue(socket.isClosed, "stop must retain and close the pending dial")
        transport.close()
    }

    @Test
    fun staleAcceptFailureCannotClearAConcurrentlyReboundListener() = runBlocking {
        val acceptEntered = CountDownLatch(1)
        val detached = CountDownLatch(1)
        val releaseDetach = CountDownLatch(1)
        val restartReachedResourceCheck = CountDownLatch(1)
        val starts = AtomicInteger()
        val first = SignallingAcceptServerSocket(acceptEntered)
        val second = TrackingServerSocket()
        val sockets = ArrayDeque(listOf<ServerSocket>(first, second))
        val registration = registration("listener-generation")
        val transport = JvmLanDataTransport(
            registration = registration,
            serverSocketFactory = { sockets.removeFirst() },
            beforeListenerResourceCheckForTest = {
                if (starts.getAndIncrement() > 0) restartReachedResourceCheck.countDown()
            },
            afterListenerDetachForTest = {
                detached.countDown()
                awaitIgnoringInterrupt(releaseDetach)
            }
        )

        assertTrue(transport.start().isSuccess)
        val collector = launch(Dispatchers.Default) {
            runCatching { transport.incomingConnections().collect() }
        }
        await(acceptEntered, "accept loop entry")

        first.close()
        await(detached, "old listener detachment")
        val restart = async(Dispatchers.Default) { transport.start() }
        await(restartReachedResourceCheck, "replacement listener resource check")
        assertFalse(restart.isCompleted, "publication must wait for old-generation state cleanup")
        assertEquals(1L, second.bound.count, "replacement must not bind during old-generation cleanup")

        releaseDetach.countDown()
        await(second.bound, "replacement listener bind")
        assertTrue(withTimeout(TEST_TIMEOUT_MS) { restart.await() }.isSuccess)
        assertEquals(second.localPort, transport.tcpPort.value)
        assertEquals(second.localPort, registration.tcpPort)

        withTimeout(TEST_TIMEOUT_MS) { collector.join() }
        transport.close()
    }

    @Test
    fun failedListenerCloseBlocksRestartUntilStopRetryReleasesIt() = runBlocking {
        val first = FailOnceCloseServerSocket()
        val second = TrackingServerSocket()
        val sockets = ArrayDeque(listOf<ServerSocket>(first, second))
        val transport = JvmLanDataTransport(
            registration = registration("listener-cleanup-retry"),
            serverSocketFactory = { sockets.removeFirst() }
        )

        assertTrue(transport.start().isSuccess)
        assertFailsWith<IllegalStateException> { transport.stop() }
        assertTrue(
            transport.start().isFailure,
            "restart must fail closed while listener cleanup remains uncertain"
        )

        transport.stop()
        assertTrue(transport.start().isSuccess)
        transport.close()
    }

    @Test
    fun failedBindCleanupIsRetainedAndBlocksRestartUntilStopRetry() = runBlocking {
        val first = FailBindAndFirstCloseServerSocket()
        val second = TrackingServerSocket()
        val sockets = ArrayDeque(listOf<ServerSocket>(first, second))
        val transport = JvmLanDataTransport(
            registration = registration("bind-cleanup-retry"),
            serverSocketFactory = { sockets.removeFirst() }
        )

        val bindResult = transport.start()
        assertTrue(bindResult.isFailure)
        val bindFailure = requireNotNull(bindResult.exceptionOrNull())
        assertEquals(
            1,
            bindFailure.suppressed.size,
            "failure=$bindFailure closeAttempts=${first.closeAttemptCount}"
        )
        assertTrue(transport.start().isFailure, "restart must not bypass uncertain bind cleanup")
        transport.stop()
        assertTrue(first.isClosed)
        assertTrue(transport.start().isSuccess)
        transport.close()
    }

    @Test
    fun inboundAddressPolicyRejectsExcludedInterfacesButAllowsSameHostLoopback() = runBlocking {
        val selected = AtomicReference(InetAddress.getByName("192.0.2.1"))
        val transport = JvmLanDataTransport(
            registration = registration("inbound-interface-policy"),
            selectedLanAddress = { selected.get() }
        )
        assertFalse(
            transport.isInboundAddressAllowedForTest(
                actual = InetAddress.getByName("198.51.100.2"),
                remote = InetAddress.getByName("198.51.100.3")
            ),
            "a non-selected externally reachable interface must be rejected"
        )
        assertTrue(transport.start().isSuccess)
        val accepted = async(Dispatchers.Default) {
            withTimeout(TEST_TIMEOUT_MS) { transport.incomingConnections().first() }
        }
        val allowed = Socket(
            InetAddress.getLoopbackAddress(),
            requireNotNull(transport.tcpPort.value)
        )
        val raw = accepted.await()

        raw.close()
        allowed.close()
        transport.close()
    }

    private fun registration(id: String) = LanServiceRegistration(
        appId = AppId("ownership-$id"),
        localPeerId = PeerId("local-$id"),
        deviceName = "local",
        platform = Platform.JVM_DESKTOP
    )

    private fun peer(id: String) = InternalPeer(
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

    private suspend fun await(latch: CountDownLatch, what: String) {
        val completed = withContext(Dispatchers.IO) {
            latch.await(TEST_TIMEOUT_MS, TimeUnit.MILLISECONDS)
        }
        assertTrue(completed, "timed out waiting for $what")
    }

    private companion object {
        const val TEST_TIMEOUT_MS: Long = 5_000

        fun awaitIgnoringInterrupt(latch: CountDownLatch) {
            while (true) {
                try {
                    latch.await()
                    return
                } catch (_: InterruptedException) {
                    // Reproduce blocking socket work that ignores interruption.
                }
            }
        }
    }
}
