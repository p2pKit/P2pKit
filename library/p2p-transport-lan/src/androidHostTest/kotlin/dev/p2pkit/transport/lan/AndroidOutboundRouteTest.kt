package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.OutboundRoute
import dev.p2pkit.core.transport.OutboundRouteConnection
import dev.p2pkit.core.transport.OutboundRouteUnavailable
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportHint
import java.io.IOException
import java.net.ConnectException
import java.net.Inet6Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketAddress
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Socket-level route evidence and ownership, independent of discovery/admission authentication tests. */
class AndroidOutboundRouteTest {
    @Test
    fun capturesOnlyActualWinningNumericDestinationAndSurvivesOriginalClose() = runBlocking<Unit> {
        val actual = endpoint(7, 40_123)
        val refused = RouteSocket(connectFailure = ConnectException("refused first candidate"))
        val winner = RouteSocket(actual)
        val replay = RouteSocket(actual)
        val sockets = ArrayDeque(listOf(refused, winner, replay))
        val transport = AndroidLanDataTransport(registration(), socketFactory = { sockets.removeFirst() })
        val hints = mutableListOf(hint(2, 41), hint(3, 42))
        var original: RawConnection? = null
        var fresh: RawConnection? = null
        try {
            original = transport.connect(peer(hints))
            val route = routeOf(original)
            assertSame(transport, route.transport)
            assertTrue(refused.isClosed, "failed first candidate must already be retired")
            assertEquals(42, winner.attempted?.port)
            assertTrue(winner.timeout in 1..LanConstants.TCP_CANDIDATE_CONNECT_TIMEOUT_MS)
            original.close()
            assertTrue(winner.isClosed)
            assertTrue(route.isCurrent, "route cannot depend on the original raw remaining open")
            // A fresh route call has no peer/hints to reread, even when the input list is replaced.
            hints.clear()
            hints += TransportHint(TransportKind.LAN, "never-resolve.invalid", 65_000)
            fresh = route.connect(900)
            assertEquals(actual, replay.attempted)
            assertFalse(assertNotNull(replay.attempted).isUnresolved)
            assertTrue(replay.timeout in 1..900)
            assertSame(route, routeOf(fresh))
            assertTrue(sockets.isEmpty(), "one failed candidate, one winner and one fresh replay only")
        } finally {
            fresh?.close()
            original?.close()
            transport.close()
            listOf(refused, winner, replay).forEach(RouteSocket::disposeFromFixture)
        }
    }

    @Test
    fun missingOrThrowingOptionalNumericObservationDoesNotBreakOrdinarySuccess() = runBlocking<Unit> {
        listOf(false, true).forEach { throws ->
            val socket = RouteSocket(observed = null, observationThrows = throws)
            val transport = AndroidLanDataTransport(registration(), socketFactory = { socket })
            var raw: RawConnection? = null
            try {
                raw = transport.connect(peer())
                assertEquals(ConnectionState.Connected, raw.state.value)
                assertNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
                assertEquals(LanConstants.TCP_CONNECT_TIMEOUT_MS, socket.timeout)
            } finally {
                raw?.close()
                transport.close()
                socket.disposeFromFixture()
            }
        }
    }

    @Test
    fun optionalNumericObservationCancellationClosesOrdinaryAndReplayDials() = runBlocking<Unit> {
        for (isReplay in listOf(false, true)) {
            // Ordinary dial logs first, then extracts capability; replay reads back before wrapping/logging.
            val original = RouteSocket(cancelObservationAt = if (isReplay) null else 2)
            val replay = RouteSocket(cancelObservationAt = 1)
            val sockets = ArrayDeque(listOf(original, replay))
            val transport = AndroidLanDataTransport(registration(), socketFactory = { sockets.removeFirst() })
            try {
                if (isReplay) {
                    val raw = transport.connect(peer())
                    val route = routeOf(raw)
                    raw.close()
                    assertFailsWith<CancellationException> { route.connect(500) }
                    assertTrue(replay.isClosed)
                    assertTrue(sockets.isEmpty())
                } else {
                    assertFailsWith<CancellationException> { transport.connect(peer()) }
                    assertTrue(original.isClosed)
                    assertEquals(1, sockets.size)
                }
            } finally {
                transport.close()
                original.disposeFromFixture()
                replay.disposeFromFixture()
            }
        }
    }

    @Test
    fun stopAndStopStartAbaInvalidateOriginalGenerationBeforeSocketAllocation() = runBlocking<Unit> {
        val allocations = AtomicInteger()
        val socket = RouteSocket()
        val transport = AndroidLanDataTransport(
            registration(), role = LanRole.DialOnly,
            socketFactory = { allocations.incrementAndGet(); socket }
        )
        try {
            val raw = transport.connect(peer())
            val route = routeOf(raw)
            raw.close()
            transport.stop()
            assertFalse(route.isCurrent)
            assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
            assertTrue(transport.start().isSuccess)
            assertFalse(route.isCurrent, "stop/start must not revive the old capability")
            assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
            assertEquals(1, allocations.get())
        } finally {
            transport.close()
            socket.disposeFromFixture()
        }
    }

    @Test
    fun exactReplayRejectsMissingOrDifferentReadbackAndRetiresTheSocket() = runBlocking<Unit> {
        listOf(null, endpoint(8, 40_001), endpoint(7, 40_002)).forEach { observed ->
            val original = RouteSocket()
            val replay = RouteSocket(observed)
            val sockets = ArrayDeque(listOf(original, replay))
            val transport = AndroidLanDataTransport(registration(), socketFactory = { sockets.removeFirst() })
            try {
                val raw = transport.connect(peer())
                val route = routeOf(raw)
                raw.close()
                assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
                assertTrue(replay.isClosed, "readback refusal must retire before permitting fallback")
                assertTrue(sockets.isEmpty(), "route replay must never allocate an alternative candidate")
            } finally {
                transport.close()
                original.disposeFromFixture()
                replay.disposeFromFixture()
            }
        }
    }

    @Test
    fun uncertainCleanupIsRetainedAndNeverCertifiesFallback() = runBlocking<Unit> {
        val original = RouteSocket()
        val replay = RouteSocket(connectFailure = ConnectException("refused"), closeFailures = 1)
        val sockets = ArrayDeque(listOf(original, replay))
        val transport = AndroidLanDataTransport(registration(), socketFactory = { sockets.removeFirst() })
        try {
            val raw = transport.connect(peer())
            val route = routeOf(raw)
            raw.close()
            val failure = assertFailsWith<ConnectException> { route.connect(500) }
            assertTrue(failure.suppressed.any { it is IOException })
            assertFalse(replay.isClosed, "fixture left native ownership unfinished")
            assertEquals(1, replay.closeAttempts.get())
            transport.stop()
            assertTrue(replay.isClosed, "transport stop must retry its retained cleanup ledger")
            assertEquals(2, replay.closeAttempts.get())
            assertTrue(sockets.isEmpty())
        } finally {
            transport.close()
            original.disposeFromFixture()
            replay.disposeFromFixture()
        }
    }

    @Test
    fun generationChecksCoverAllocationPendingConnectAndFinalHandoff() = runBlocking<Unit> {
        for (boundary in Boundary.entries) {
            val armed = AtomicBoolean()
            val allocations = AtomicInteger()
            val original = RouteSocket()
            lateinit var transport: AndroidLanDataTransport
            val replay = RouteSocket(onConnect = {
                if (boundary == Boundary.Pending) runBlocking { transport.stop() }
            })
            transport = AndroidLanDataTransport(
                registration(), role = LanRole.DialOnly,
                socketFactory = {
                    if (allocations.getAndIncrement() == 0) original else {
                        if (boundary == Boundary.Allocation) runBlocking { transport.stop() }
                        replay
                    }
                },
                beforeDialOwnershipHandoffForTest = {
                    if (armed.get() && boundary == Boundary.Handoff) runBlocking { transport.stop() }
                }
            )
            try {
                val raw = transport.connect(peer())
                val route = routeOf(raw)
                raw.close()
                armed.set(true)
                assertFailsWith<OutboundRouteUnavailable> { route.connect(900) }
                assertTrue(replay.isClosed, "stop at $boundary must close the fresh owned socket")
                assertFalse(route.isCurrent)
                assertEquals(2, allocations.get())
            } finally {
                transport.close()
                original.disposeFromFixture()
                replay.disposeFromFixture()
            }
        }
    }

    @Test
    fun callerCancellationPropagatesWithoutFallbackAndClosesReplay() = runBlocking<Unit> {
        val original = RouteSocket()
        val replay = RouteSocket(connectFailure = CancellationException("cancel during connect"))
        val sockets = ArrayDeque(listOf(original, replay))
        val transport = AndroidLanDataTransport(registration(), socketFactory = { sockets.removeFirst() })
        try {
            val raw = transport.connect(peer())
            val route = routeOf(raw)
            raw.close()
            assertFailsWith<CancellationException> { route.connect(500) }
            assertTrue(replay.isClosed)
            assertTrue(sockets.isEmpty())
        } finally {
            transport.close()
            original.disposeFromFixture()
            replay.disposeFromFixture()
        }
    }

    @Test
    fun scopedIpv6AddressAndExactPortArePreservedWithoutDns() = runBlocking<Unit> {
        val bytes = ByteArray(16).also { it[0] = 0xfe.toByte(); it[1] = 0x80.toByte(); it[15] = 9 }
        val actual = InetSocketAddress(Inet6Address.getByAddress(null, bytes, 17), 54_321)
        val original = RouteSocket(actual)
        val replay = RouteSocket(actual)
        val sockets = ArrayDeque(listOf(original, replay))
        val transport = AndroidLanDataTransport(registration(), socketFactory = { sockets.removeFirst() })
        var fresh: RawConnection? = null
        try {
            val raw = transport.connect(peer())
            val route = routeOf(raw)
            raw.close()
            fresh = route.connect(Long.MAX_VALUE)
            val address = assertIs<Inet6Address>(assertNotNull(replay.attempted).address)
            assertEquals(17, address.scopeId)
            assertContentEquals(bytes, address.address)
            assertEquals(54_321, replay.attempted?.port)
            assertTrue(replay.timeout in 1..LanConstants.TCP_CONNECT_TIMEOUT_MS)
        } finally {
            fresh?.close()
            transport.close()
            original.disposeFromFixture()
            replay.disposeFromFixture()
        }
    }

    @Test
    fun nativeLoopbackSuccessReplaysAndCleanRefusalIsObservedBeforeFallback() = runBlocking<Unit> {
        val listener = ServerSocket(0, 8, InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1)))
        val sockets = mutableListOf<Socket>()
        val transport = AndroidLanDataTransport(registration(), socketFactory = { Socket().also(sockets::add) })
        var raw: RawConnection? = null
        var fresh: RawConnection? = null
        var accepted: Socket? = null
        try {
            raw = transport.connect(peer(listOf(TransportHint(TransportKind.LAN, "localhost", listener.localPort))))
            accepted = withContext(Dispatchers.IO) { listener.accept() }
            val route = routeOf(raw)
            raw.write(byteArrayOf(37))
            assertEquals(37, withContext(Dispatchers.IO) { assertNotNull(accepted).getInputStream().read() })
            raw.close()
            accepted.close()
            fresh = route.connect(1_500)
            accepted = withContext(Dispatchers.IO) { listener.accept() }
            fresh.write(byteArrayOf(42))
            assertEquals(42, withContext(Dispatchers.IO) { assertNotNull(accepted).getInputStream().read() })
            assertEquals(listener.localPort, sockets.last().port)
            assertEquals(sockets.first().inetAddress, sockets.last().inetAddress)
            fresh.close()
            accepted.close()
            listener.close()
            assertFailsWith<OutboundRouteUnavailable> { route.connect(1_500) }
            assertEquals(3, sockets.size)
            assertTrue(sockets.last().isClosed, "actual refused TCP socket must be observed closed before fallback")
        } finally {
            raw?.close()
            fresh?.close()
            accepted?.close()
            listener.close()
            transport.close()
            sockets.forEach(Socket::close)
        }
    }

    @Test
    fun inboundConnectionNeverExposesRemoteEphemeralPortAsAnOutboundRoute() = runBlocking<Unit> {
        val transport = AndroidLanDataTransport(registration())
        var outbound: Socket? = null
        var accepted: RawConnection? = null
        val incoming = async(Dispatchers.IO) { transport.incomingConnections().first() }
        try {
            transport.start().getOrThrow()
            outbound = withContext(Dispatchers.IO) { Socket("127.0.0.1", assertNotNull(transport.tcpPort.value)) }
            accepted = withTimeout(5_000) { incoming.await() }
            assertNull((accepted as? OutboundRouteConnection)?.outboundRoute)
        } finally {
            incoming.cancel()
            accepted?.close()
            outbound?.close()
            transport.close()
            withTimeout(5_000) { incoming.join() }
        }
    }

    private enum class Boundary { Allocation, Pending, Handoff }

    private class RouteSocket(
        private val observed: InetSocketAddress? = endpoint(7, 40_001),
        private val observationThrows: Boolean = false,
        private val cancelObservationAt: Int? = null,
        private val connectFailure: Throwable? = null,
        private val closeFailures: Int = 0,
        private val onConnect: () -> Unit = {}
    ) : Socket() {
        var attempted: InetSocketAddress? = null
        var timeout: Int = 0
        val closeAttempts = AtomicInteger()
        private val observations = AtomicInteger()

        override fun connect(endpoint: SocketAddress?, timeout: Int) {
            attempted = endpoint as InetSocketAddress
            this.timeout = timeout
            onConnect()
            connectFailure?.let { throw it }
        }
        override fun setTcpNoDelay(on: Boolean) = Unit
        override fun getRemoteSocketAddress(): SocketAddress? {
            if (observations.incrementAndGet() == cancelObservationAt) {
                throw CancellationException("injected numeric observation cancellation")
            }
            if (observationThrows) throw IllegalStateException("optional address observation unavailable")
            return observed
        }
        override fun getLocalSocketAddress(): SocketAddress = endpoint(1, 9_001)
        override fun close() {
            if (closeAttempts.getAndIncrement() < closeFailures) throw IOException("injected unfinished socket cleanup")
            super.close()
        }
        fun disposeFromFixture() = super.close()
    }

    private fun routeOf(raw: RawConnection): OutboundRoute =
        assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)

    private fun registration() = LanServiceRegistration(
        AppId("outbound-route"), PeerId("route-local"), "route-local", Platform.ANDROID
    )

    private fun peer(hints: List<TransportHint> = listOf(hint(7, 40_001))) = InternalPeer(
        Peer(PeerId("route-peer"), "remote", Platform.ANDROID, setOf(TransportKind.LAN)), hints
    )

    private companion object {
        fun hint(lastOctet: Int, port: Int) = TransportHint(TransportKind.LAN, "127.0.0.$lastOctet", port)
        fun endpoint(lastOctet: Int, port: Int) =
            InetSocketAddress(InetAddress.getByAddress(byteArrayOf(127, 0, 0, lastOctet.toByte())), port)
    }
}
