package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

class TransportManagerTest {

    private val peer = InternalPeer(
        publicPeer = Peer(
            id = PeerId("peer-1"),
            name = "Test",
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = emptyList()
    )

    @Test
    fun selectsHighestPriorityTransport() {
        val low = FakeTransport(TransportKind.LAN, priority = 1, canConnect = true)
        val high = FakeTransport(TransportKind.LAN, priority = 10, canConnect = true)
        val mid = FakeTransport(TransportKind.LAN, priority = 5, canConnect = true)

        val manager = TransportManager(listOf(low, high, mid))
        val chosen = manager.selectBestTransport(peer)

        assertSame(high, chosen)
    }

    @Test
    fun ignoresTransportsThatCannotConnect() {
        val unreachable = FakeTransport(TransportKind.LAN, priority = 100, canConnect = false)
        val ok = FakeTransport(TransportKind.LAN, priority = 1, canConnect = true)

        val manager = TransportManager(listOf(unreachable, ok))
        val chosen = manager.selectBestTransport(peer)

        assertSame(ok, chosen)
    }

    @Test
    fun throwsNoTransportAvailableWhenNoneMatch() {
        val unreachable = FakeTransport(TransportKind.LAN, priority = 1, canConnect = false)
        val manager = TransportManager(listOf(unreachable))

        val ex = assertFailsWith<P2pError.NoTransportAvailable> {
            manager.selectBestTransport(peer)
        }
        assertEquals(peer.publicPeer, ex.peer)
    }

    @Test
    fun throwsNoTransportAvailableForEmptyTransportList() {
        val manager = TransportManager(emptyList())

        val ex = assertFailsWith<P2pError.NoTransportAvailable> {
            manager.selectBestTransport(peer)
        }
        assertEquals(peer.publicPeer, ex.peer)
    }

    @Test
    fun equalPrioritiesUseKindThenRegistrationOrderDeterministically() {
        val ble = FakeTransport(TransportKind.BLE, priority = 10, canConnect = true)
        val firstLan = FakeTransport(TransportKind.LAN, priority = 10, canConnect = true)
        val secondLan = FakeTransport(TransportKind.LAN, priority = 10, canConnect = true)

        assertSame(
            firstLan,
            TransportManager(listOf(ble, firstLan, secondLan)).selectBestTransport(peer)
        )
    }

    @Test
    fun providerReachabilityFailureIsTypedAndPreservesCause() {
        val cause = IllegalStateException("provider reachability failed")
        val manager = TransportManager(
            listOf(ThrowingSelectionTransport(FailurePoint.CAN_CONNECT, cause))
        )

        val failure = assertFailsWith<P2pError.ConnectionFailed> {
            manager.selectBestTransport(peer)
        }

        assertSame(cause, failure.cause)
        assertTrue(failure.reason.contains("registration #0"))
    }

    @Test
    fun providerSelectionMetadataFailureIsTypedAndPreservesCause() {
        listOf(FailurePoint.PRIORITY, FailurePoint.TYPE).forEach { point ->
            val cause = IllegalArgumentException("provider $point failed")
            val manager = TransportManager(listOf(ThrowingSelectionTransport(point, cause)))

            val failure = assertFailsWith<P2pError.ConnectionFailed> {
                manager.selectBestTransport(peer)
            }

            assertSame(cause, failure.cause)
            assertTrue(failure.reason.contains("registration #0"))
        }
    }

    @Test
    fun providerCancellationIsNeverWrapped() {
        val cancellation = CancellationException("selection cancelled")
        val manager = TransportManager(
            listOf(ThrowingSelectionTransport(FailurePoint.CAN_CONNECT, cancellation))
        )

        val thrown = assertFailsWith<CancellationException> {
            manager.selectBestTransport(peer)
        }

        assertSame(cancellation, thrown)
    }

    private class FakeTransport(
        override val type: TransportKind,
        override val priority: Int,
        private val canConnect: Boolean
    ) : DataTransport {
        override fun canConnect(peer: InternalPeer): Boolean = canConnect
        override suspend fun connect(peer: InternalPeer): RawConnection = error("not used")
        override fun incomingConnections(): Flow<RawConnection> = emptyFlow()
        override suspend fun stop() = Unit
        override suspend fun close() = Unit
    }

    private enum class FailurePoint { CAN_CONNECT, PRIORITY, TYPE }

    private class ThrowingSelectionTransport(
        private val failurePoint: FailurePoint,
        private val failure: Throwable
    ) : DataTransport {
        override val type: TransportKind
            get() = if (failurePoint == FailurePoint.TYPE) throw failure else TransportKind.LAN

        override val priority: Int
            get() = if (failurePoint == FailurePoint.PRIORITY) throw failure else 100

        override fun canConnect(peer: InternalPeer): Boolean {
            if (failurePoint == FailurePoint.CAN_CONNECT) throw failure
            return true
        }

        override suspend fun connect(peer: InternalPeer): RawConnection = error("not used")
        override fun incomingConnections(): Flow<RawConnection> = emptyFlow()
        override suspend fun stop() = Unit
        override suspend fun close() = Unit
    }
}
