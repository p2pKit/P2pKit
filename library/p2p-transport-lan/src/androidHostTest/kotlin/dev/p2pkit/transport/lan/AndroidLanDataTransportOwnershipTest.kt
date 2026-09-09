package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InboundConnectionAdmission
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportHint
import java.io.IOException
import java.net.BindException
import java.net.ConnectException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketAddress
import java.net.SocketException
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
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

/** Android-host proof for the socket ownership logic mirrored from the JVM transport. */
class AndroidLanDataTransportOwnershipTest {

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

    private open class ImmediateConnectSocket(
        remoteHost: String = "127.0.0.2",
        localHost: String = "127.0.0.1",
        private val optionFailure: Throwable? = null,
        private val failFirstClose: Boolean = false
    ) : Socket() {
        private val remote = InetAddress.getByName(remoteHost)
        private val local = InetAddress.getByName(localHost)
        private val closeAttempts = AtomicInteger()
        val optionAttempts = AtomicInteger()
        @Volatile private var noDelay = false

        override fun connect(endpoint: SocketAddress?, timeout: Int) = Unit

        override fun setTcpNoDelay(on: Boolean) {
            optionAttempts.incrementAndGet()
            optionFailure?.let { throw it }
            noDelay = on
        }

        override fun getTcpNoDelay(): Boolean = noDelay
        override fun getInetAddress(): InetAddress = remote
        override fun getLocalAddress(): InetAddress = local
        override fun getRemoteSocketAddress(): SocketAddress = InetSocketAddress(remote, 9)
        override fun getLocalSocketAddress(): SocketAddress = InetSocketAddress(local, 9_001)

        override fun close() {
            if (closeAttempts.getAndIncrement() == 0 && failFirstClose) {
                throw IOException("injected option cleanup failure")
            }
            super.close()
        }

        // Emergency fixture disposal is not evidence that production released the socket.
        fun closeFromFixture() = super.close()
    }

    private class ScriptedAcceptServerSocket(
        private val accepted: List<Socket>,
        private val gates: Map<Int, CountDownLatch> = emptyMap()
    ) : TrackingServerSocket() {
        val acceptEntries = List(accepted.size + 1) { CountDownLatch(1) }
        private val nextAccept = AtomicInteger()

        override fun accept(): Socket {
            val index = nextAccept.getAndIncrement()
            acceptEntries.getOrNull(index)?.countDown()
            gates[index]?.let { gate ->
                check(gate.await(TEST_TIMEOUT_MS, TimeUnit.MILLISECONDS)) { "fixture accept gate timed out" }
            }
            if (isClosed) throw SocketException("fixture listener closed")
            return accepted.getOrNull(index) ?: super.accept()
        }

        override fun close() {
            try {
                super.close()
            } finally {
                gates.values.forEach(CountDownLatch::countDown)
            }
        }
    }

    private class RecordingRouteSocket : ImmediateConnectSocket() {
        var boundEndpoint: SocketAddress? = null

        override fun bind(bindpoint: SocketAddress?) {
            boundEndpoint = bindpoint
        }

        override fun connect(endpoint: SocketAddress?, timeout: Int) = Unit
    }

    private open class FailingRouteBindSocket : Socket() {
        override fun bind(bindpoint: SocketAddress?) {
            throw BindException("injected route bind failure")
        }
    }

    private class FailRouteBindAndFirstCloseSocket : FailingRouteBindSocket() {
        private val closeAttempts = AtomicInteger()

        override fun close() {
            if (closeAttempts.getAndIncrement() == 0) {
                throw IOException("injected route socket cleanup failure")
            }
            super.close()
        }
    }

    private class FailOnceCloseConnectSocket : Socket() {
        private var closeAttempts = 0

        override fun connect(endpoint: SocketAddress?, timeout: Int) {
            throw ConnectException("injected refusal")
        }

        override fun close() {
            if (closeAttempts++ == 0) throw IOException("injected candidate cleanup failure")
            super.close()
        }
    }

    @Test
    fun cancellationWhileBindCompletesClosesTheUnpublishedListener() = runBlocking {
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val socket = GatedBindServerSocket(entered, release)
        val registration = registration("cancelled-bind")
        val transport = AndroidLanDataTransport(
            registration = registration,
            serverSocketFactory = { socket }
        )

        val starter = launch(Dispatchers.Default) { transport.start().getOrThrow() }
        await(entered, "listener bind entry")
        starter.cancel()
        release.countDown()
        withTimeout(TEST_TIMEOUT_MS) { starter.join() }

        assertTrue(starter.isCancelled)
        assertTrue(socket.isClosed)
        assertNull(transport.tcpPort.value)
        assertEquals(0, registration.tcpPort)
        transport.stop()
    }

    @Test
    fun stopAtFinalDialHandoffCannotReturnAClosedRawConnection() = runBlocking {
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val socket = ImmediateConnectSocket()
        val transport = AndroidLanDataTransport(
            registration = registration("dial-handoff"),
            socketFactory = { socket },
            beforeDialOwnershipHandoffForTest = {
                entered.countDown()
                awaitIgnoringInterrupt(release)
            }
        )

        val result = async(Dispatchers.Default) {
            runCatching { transport.connect(peer("android-dial-peer")) }
        }
        await(entered, "final dial ownership handoff")
        transport.stop()
        release.countDown()

        assertIs<P2pError.ConnectionFailed>(
            withTimeout(TEST_TIMEOUT_MS) { result.await() }.exceptionOrNull()
        )
        assertTrue(socket.isClosed)
        assertTrue(socket.tcpNoDelay, "TCP_NODELAY must be set before the final handoff")
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
        val transport = AndroidLanDataTransport(
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
        val transport = AndroidLanDataTransport(
            registration = registration("listener-cleanup-retry"),
            serverSocketFactory = { sockets.removeFirst() }
        )

        assertTrue(transport.start().isSuccess)
        assertFailsWith<IllegalStateException> { transport.stop() }
        assertTrue(transport.start().isFailure)
        transport.stop()
        assertTrue(transport.start().isSuccess)
        transport.close()
    }

    @Test
    fun failedBindCleanupIsRetainedAndBlocksRestartUntilStopRetry() = runBlocking {
        val first = FailBindAndFirstCloseServerSocket()
        val second = TrackingServerSocket()
        val sockets = ArrayDeque(listOf<ServerSocket>(first, second))
        val transport = AndroidLanDataTransport(
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
        assertTrue(transport.start().isFailure)
        transport.stop()
        assertTrue(first.isClosed)
        assertTrue(transport.start().isSuccess)
        transport.close()
    }

    @Test
    fun inboundAddressPolicyRejectsExcludedInterfacesButAllowsSameHostLoopback() = runBlocking {
        val routeState = AndroidLanNetworkState().apply {
            select(hotspotTarget(address = "192.0.2.1"))
        }
        val transport = AndroidLanDataTransport(
            registration = registration("inbound-interface-policy"),
            networkState = routeState
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

    @Test
    fun inboundPerSourceQuotaRejectsBeforeQueueAndRecoversAfterRelease() = runBlocking {
        val transport = AndroidLanDataTransport(registration("per-source-admission"))
        val clients = mutableListOf<Socket>()
        try {
            assertTrue(transport.start().isSuccess)
            val port = requireNotNull(transport.tcpPort.value)
            val received = Channel<RawConnection>(Channel.UNLIMITED)
            val collector = launch(Dispatchers.Default) {
                transport.incomingConnections().collect(received::send)
            }
            repeat(MAX_PRE_HANDSHAKE_CONNECTIONS_PER_SOURCE + 1) {
                clients += Socket(InetAddress.getLoopbackAddress(), port)
            }

            val admitted = withTimeout(TEST_TIMEOUT_MS) {
                List(MAX_PRE_HANDSHAKE_CONNECTIONS_PER_SOURCE) { received.receive() }
            }
            val refused = clients.last()
            refused.soTimeout = 2_000
            assertEquals(-1, refused.getInputStream().read())

            assertIs<InboundConnectionAdmission>(admitted.first())
                .releasePreHandshakeAdmission()
            clients += Socket(InetAddress.getLoopbackAddress(), port)
            withTimeout(TEST_TIMEOUT_MS) { received.receive() }.close()
            admitted.forEach { it.close() }
            collector.cancelAndJoin()
        } finally {
            clients.forEach { runCatching { it.close() } }
            transport.close()
        }
    }

    @Test
    fun failedCandidateCleanupPreventsOpeningAnotherCandidate() = runBlocking {
        val first = FailOnceCloseConnectSocket()
        val creations = AtomicInteger()
        val transport = AndroidLanDataTransport(
            registration = registration("candidate-cleanup"),
            socketFactory = {
                if (creations.getAndIncrement() == 0) first else ImmediateConnectSocket()
            }
        )

        val failure = assertFailsWith<P2pError.ConnectionFailed> {
            transport.connect(peerWithHosts("android-candidate", "192.168.1.20", "192.168.1.21"))
        }

        assertTrue("candidate cleanup failed" in failure.reason)
        assertEquals(1, creations.get(), "uncertain socket ownership must fail closed")
        assertEquals(2, failure.suppressed.size)
        transport.stop()
        assertTrue(first.isClosed)
        transport.close()
    }

    @Test
    fun productionRouteStateFailsClosedBeforeCreatingAnUnboundSocket() = runBlocking {
        val creations = AtomicInteger()
        val transport = AndroidLanDataTransport(
            registration = registration("missing-route"),
            networkState = AndroidLanNetworkState(),
            socketFactory = {
                creations.incrementAndGet()
                ImmediateConnectSocket()
            }
        )

        val failure = assertFailsWith<P2pError.ConnectionFailed> {
            transport.connect(peer("android-missing-route-peer"))
        }

        assertTrue("No Android LAN route" in failure.reason)
        assertEquals(0, creations.get(), "an unrestricted socket must never be created")
        transport.close()
    }

    @Test
    fun hotspotFallbackBindsTheSelectedLocalAddressBeforeConnect() = runBlocking {
        val resolverCalls = AtomicInteger()
        val routeState = AndroidLanNetworkState {
            resolverCalls.incrementAndGet()
            null
        }.apply {
            select(
                hotspotTarget()
            )
        }
        val socket = RecordingRouteSocket()
        val transport = AndroidLanDataTransport(
            registration = registration("hotspot-route"),
            networkState = routeState,
            socketFactory = { selectedNetwork ->
                assertNull(selectedNetwork, "AP fallback has no ConnectivityManager Network")
                socket
            }
        )

        val raw = transport.connect(peer("android-hotspot-peer"))

        val bound = assertIs<InetSocketAddress>(socket.boundEndpoint)
        assertEquals("192.168.43.1", bound.address.hostAddress)
        assertEquals(0, bound.port)
        assertEquals(0, resolverCalls.get(), "the discovery-owned route must take precedence")
        raw.close()
        transport.close()
    }

    @Test
    fun manualPeerDialResolvesAndBindsARouteWithoutDiscovery() = runBlocking {
        val resolverCalls = AtomicInteger()
        val routeState = AndroidLanNetworkState {
            resolverCalls.incrementAndGet()
            hotspotTarget()
        }
        val socket = RecordingRouteSocket()
        val transport = AndroidLanDataTransport(
            registration = registration("manual-route"),
            networkState = routeState,
            socketFactory = { socket }
        )

        val raw = transport.connect(peer("android-manual-peer"))

        val bound = assertIs<InetSocketAddress>(socket.boundEndpoint)
        assertEquals("192.168.43.1", bound.address.hostAddress)
        assertEquals(1, resolverCalls.get())
        raw.close()
        transport.close()
    }

    @Test
    fun idleRouteClearForcesTheNextManualDialToResolveCurrentTopology() = runBlocking {
        val staleTarget = hotspotTarget(address = "192.168.43.1", interfaceName = "softap0")
        val currentTarget = hotspotTarget(address = "192.168.50.1", interfaceName = "softap1")
        val resolverCalls = AtomicInteger()
        val routeState = AndroidLanNetworkState {
            resolverCalls.incrementAndGet()
            currentTarget
        }.apply { select(staleTarget) }
        val socket = RecordingRouteSocket()
        val transport = AndroidLanDataTransport(
            registration = registration("manual-route-after-idle"),
            networkState = routeState,
            socketFactory = { socket }
        )

        // This is the discovery coordinator's true-idle ownership boundary.
        routeState.clear()
        val raw = transport.connect(peer("android-manual-peer-after-idle"))

        val bound = assertIs<InetSocketAddress>(socket.boundEndpoint)
        assertEquals("192.168.50.1", bound.address.hostAddress)
        assertEquals(1, resolverCalls.get())
        raw.close()
        transport.close()
    }

    @Test
    fun routeBindFailuresCloseEveryCandidateAndRemainTyped() = runBlocking {
        val sockets = mutableListOf<FailingRouteBindSocket>()
        val transport = AndroidLanDataTransport(
            registration = registration("route-bind-failure"),
            networkState = AndroidLanNetworkState { hotspotTarget() },
            socketFactory = {
                FailingRouteBindSocket().also(sockets::add)
            }
        )

        val failure = assertFailsWith<P2pError.ConnectionFailed> {
            transport.connect(
                peerWithHosts(
                    "android-route-bind-failure-peer",
                    "192.168.43.2",
                    "192.168.43.3"
                )
            )
        }

        assertTrue("route setup failed" in failure.reason)
        assertEquals(2, sockets.size)
        assertTrue(sockets.all(Socket::isClosed))
        transport.close()
    }

    @Test
    fun routeBindCleanupFailureBlocksFurtherCandidatesUntilStopRetry() = runBlocking {
        val first = FailRouteBindAndFirstCloseSocket()
        val creations = AtomicInteger()
        val transport = AndroidLanDataTransport(
            registration = registration("route-cleanup-failure"),
            networkState = AndroidLanNetworkState { hotspotTarget() },
            socketFactory = {
                creations.incrementAndGet()
                first
            }
        )

        val failure = assertFailsWith<P2pError.ConnectionFailed> {
            transport.connect(
                peerWithHosts(
                    "android-route-cleanup-failure-peer",
                    "192.168.43.2",
                    "192.168.43.3"
                )
            )
        }

        assertTrue("route setup cleanup failed" in failure.reason)
        assertEquals(1, creations.get(), "uncertain route ownership must fail closed")
        transport.stop()
        assertTrue(first.isClosed)
        transport.close()
    }

    @Test
    fun dialSocketOptionFailureIsTypedAndClosedBeforeRecovery() = runBlocking<Unit> {
        val failed = ImmediateConnectSocket(optionFailure = IOException("injected TCP_NODELAY failure"))
        val healthy = ImmediateConnectSocket()
        val sockets = ArrayDeque(listOf(failed, healthy))
        val transport = AndroidLanDataTransport(
            registration = registration("dial-options"),
            socketFactory = { sockets.removeFirst() }
        )
        var firstRaw: RawConnection? = null
        var recovered: RawConnection? = null
        try {
            val firstAttempt = runCatching { transport.connect(peer("dial-options-peer")) }
            firstRaw = firstAttempt.getOrNull()
            val failure = assertIs<P2pError.ConnectionFailed>(firstAttempt.exceptionOrNull())
            assertTrue("TCP_NODELAY" in failure.reason)
            assertTrue(failed.isClosed, "option failure must close the still-owned dial socket")
            assertEquals(1, failed.optionAttempts.get())

            recovered = transport.connect(peer("dial-options-peer"))
            assertTrue(healthy.tcpNoDelay)
            assertEquals(1, healthy.optionAttempts.get())
        } finally {
            firstRaw?.close()
            recovered?.close()
            transport.close()
            failed.closeFromFixture()
            healthy.closeFromFixture()
        }
    }

    @Test
    fun acceptedOptionFailureClosesWithoutConsumingASourceSlot() = runBlocking<Unit> {
        val failed = ImmediateConnectSocket(optionFailure = IOException("injected TCP_NODELAY failure"))
        val healthy = List(MAX_PRE_HANDSHAKE_CONNECTIONS_PER_SOURCE) { ImmediateConnectSocket() }
        val sockets = listOf(failed) + healthy
        val listener = ScriptedAcceptServerSocket(sockets)
        val transport = AndroidLanDataTransport(
            registration = registration("accept-options"),
            serverSocketFactory = { listener }
        )
        val received = CopyOnWriteArrayList<RawConnection>()
        val delivered = Channel<Unit>(Channel.UNLIMITED)
        val collector = launch(Dispatchers.Default) {
            transport.incomingConnections().collect { raw ->
                received += raw
                delivered.trySend(Unit)
            }
        }
        try {
            assertTrue(transport.start().isSuccess)
            await(listener.acceptEntries[sockets.size], "all option offers completed")
            withTimeout(TEST_TIMEOUT_MS) { repeat(healthy.size) { delivered.receive() } }
            assertTrue(failed.isClosed, "rejected option setter must close before the next accept")
            assertEquals(1, failed.optionAttempts.get())
            assertTrue(healthy.all { it.tcpNoDelay && !it.isClosed })
            assertTrue(healthy.all { it.optionAttempts.get() == 1 })
            assertEquals(
                List(healthy.size) { failed.inetAddress.hostAddress },
                received.map { assertIs<InboundConnectionAdmission>(it).admissionSource }
            )
        } finally {
            collector.cancel()
            transport.close()
            listener.close()
            withTimeout(TEST_TIMEOUT_MS) { collector.join() }
            received.forEach { it.close() }
            delivered.close()
            sockets.forEach(ImmediateConnectSocket::closeFromFixture)
        }
    }

    @Test
    fun failedAcceptedOptionCleanupRemainsOwnedUntilStopRetry() = runBlocking<Unit> {
        val optionFailure = IOException("injected TCP_NODELAY failure")
        val failed = ImmediateConnectSocket(optionFailure = optionFailure, failFirstClose = true)
        val first = ScriptedAcceptServerSocket(listOf(failed))
        val second = TrackingServerSocket()
        val listeners = ArrayDeque(listOf<ServerSocket>(first, second))
        val transport = AndroidLanDataTransport(
            registration = registration("accept-option-cleanup"),
            serverSocketFactory = { listeners.removeFirst() }
        )
        val received = CopyOnWriteArrayList<RawConnection>()
        val result = async(Dispatchers.Default) {
            runCatching { transport.incomingConnections().collect { received += it } }
        }
        try {
            assertTrue(transport.start().isSuccess)
            val failure = withTimeout(TEST_TIMEOUT_MS) { result.await() }.exceptionOrNull()
            assertIs<IOException>(failure)
            assertTrue(
                generateSequence<Throwable>(failure) { it.cause }.any { cause ->
                    cause.suppressed.any { it.message == "injected option cleanup failure" }
                },
                "the option and secondary cleanup failures must both remain observable"
            )
            assertFalse(failed.isClosed, "the injected failed close must not be called successful")
            assertTrue(received.isEmpty(), "a socket with unknown options must not be handed off")
            assertTrue(transport.start().isFailure, "failed accepted cleanup must block restart")
            transport.stop()
            assertTrue(failed.isClosed, "stop must retry the retained accepted socket")
            assertTrue(transport.start().isSuccess)
        } finally {
            result.cancel()
            transport.close()
            first.close()
            second.close()
            withTimeout(TEST_TIMEOUT_MS) { result.join() }
            received.forEach { it.close() }
            failed.closeFromFixture()
        }
    }

    @Test
    fun inboundBufferRejectsNewestAtTheSharedDepthAndRecoversAcrossRestart() = runBlocking<Unit> {
        val capacity = LanConstants.MAX_BUFFERED_INBOUND_CONNECTIONS
        // Core's existing admission tests independently pin its global setup gate to 16.
        assertEquals(16, capacity)
        val localHost = "192.0.2.1"
        val listeners = ArrayDeque<ServerSocket>()
        val transport = AndroidLanDataTransport(
            registration = registration("inbound-buffer"),
            networkState = AndroidLanNetworkState().apply { select(hotspotTarget(localHost)) },
            serverSocketFactory = { listeners.removeFirst() }
        )
        try {
            repeat(2) {
                val burst = List(capacity + 2) { index ->
                    ImmediateConnectSocket(
                        remoteHost = "198.51.100.${index + 1}",
                        localHost = localHost
                    )
                }
                val recovery = List(MAX_PRE_HANDSHAKE_CONNECTIONS_PER_SOURCE) {
                    ImmediateConnectSocket(
                        remoteHost = checkNotNull(burst.last().inetAddress.hostAddress),
                        localHost = localHost
                    )
                }
                val sockets = burst + recovery
                val releaseBurst = CountDownLatch(1)
                val releaseRecovery = CountDownLatch(1)
                val listener = ScriptedAcceptServerSocket(
                    sockets,
                    gates = mapOf(1 to releaseBurst, burst.size to releaseRecovery)
                )
                listeners.addLast(listener)
                val firstDelivered = CompletableDeferred<Unit>()
                val releaseConsumer = CompletableDeferred<Unit>()
                val received = CopyOnWriteArrayList<RawConnection>()
                // Notifications only: no second RawConnection buffer or flow operator in the harness.
                val delivered = Channel<Unit>(Channel.UNLIMITED)
                val collector = launch(Dispatchers.Default) {
                    transport.incomingConnections().collect { raw ->
                        received += raw
                        if (received.size == 1) {
                            firstDelivered.complete(Unit)
                            releaseConsumer.await()
                        }
                        delivered.trySend(Unit)
                    }
                }
                try {
                    assertTrue(sockets.all { socket ->
                        transport.isInboundAddressAllowedForTest(socket.localAddress, socket.inetAddress)
                    })
                    assertEquals(burst.size, burst.map { it.inetAddress.hostAddress }.distinct().size)
                    assertTrue(transport.start().isSuccess)
                    withTimeout(TEST_TIMEOUT_MS) { firstDelivered.await() }
                    releaseBurst.countDown()
                    // Entry into the next accept proves every earlier offer/drop finished.
                    await(listener.acceptEntries[burst.size], "full inbound burst processed")
                    val closedAtBoundary = burst.map(Socket::isClosed)
                    val deliveriesWhileHeld = received.size

                    // Drain the observed number even for the larger pre-fix queue before asserting.
                    // This keeps capacity evidence separate from cancellation/disposal ownership.
                    val admittedBurst = closedAtBoundary.count { closed -> !closed }
                    releaseConsumer.complete(Unit)
                    withTimeout(TEST_TIMEOUT_MS) { repeat(admittedBurst) { delivered.receive() } }
                    val burstSources = received.map { assertIs<InboundConnectionAdmission>(it).admissionSource }
                    received.forEach { it.close() }

                    releaseRecovery.countDown()
                    await(listener.acceptEntries[sockets.size], "same-source recovery offers processed")
                    val recoveryClosed = recovery.map(Socket::isClosed)
                    withTimeout(TEST_TIMEOUT_MS) {
                        repeat(recoveryClosed.count { closed -> !closed }) { delivered.receive() }
                    }
                    val recoveredSources = received.drop(admittedBurst)
                        .map { assertIs<InboundConnectionAdmission>(it).admissionSource }
                    received.drop(admittedBurst).forEach { it.close() }

                    assertEquals(1, deliveriesWhileHeld, "the direct consumer must remain held")
                    assertEquals(
                        List(capacity + 1) { false } + true,
                        closedAtBoundary,
                        "retain the delivered socket and all 16 queued sockets; close only offer 18"
                    )
                    assertEquals(burst.dropLast(1).map { checkNotNull(it.inetAddress.hostAddress) }, burstSources)
                    assertEquals(List(recovery.size) { false }, recoveryClosed, "overflow must release its source slot")
                    assertEquals(
                        List(recovery.size) { checkNotNull(burst.last().inetAddress.hostAddress) },
                        recoveredSources
                    )
                } finally {
                    releaseConsumer.complete(Unit)
                    collector.cancel()
                    try {
                        transport.stop()
                    } finally {
                        listener.close()
                        try {
                            withTimeout(TEST_TIMEOUT_MS) { collector.join() }
                        } finally {
                            received.forEach { it.close() }
                            delivered.close()
                            sockets.forEach(ImmediateConnectSocket::closeFromFixture)
                        }
                    }
                }
            }
        } finally {
            transport.close()
        }
    }

    private fun hotspotTarget(
        address: String = "192.168.43.1",
        interfaceName: String = "softap0"
    ) = AndroidLanBindTarget(
        network = null,
        interfaceName = interfaceName,
        address = InetAddress.getByName(address),
        localAddresses = emptyList(),
        fingerprint = "$interfaceName:$address/24"
    )

    private fun registration(id: String) = LanServiceRegistration(
        appId = AppId("android-ownership-$id"),
        localPeerId = PeerId("android-local-$id"),
        deviceName = "local",
        platform = Platform.ANDROID
    )

    private fun peer(id: String) = InternalPeer(
        publicPeer = Peer(
            id = PeerId(id),
            name = "remote",
            platform = Platform.ANDROID,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = listOf(
            TransportHint(TransportKind.LAN, host = "127.0.0.1", port = 9)
        )
    )

    private fun peerWithHosts(id: String, vararg hosts: String) = InternalPeer(
        publicPeer = Peer(
            id = PeerId(id),
            name = "remote",
            platform = Platform.ANDROID,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = hosts.map { host ->
            TransportHint(TransportKind.LAN, host = host, port = 9)
        }
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
