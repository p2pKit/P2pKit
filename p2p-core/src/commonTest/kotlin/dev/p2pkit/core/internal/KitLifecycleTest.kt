package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlin.concurrent.Volatile
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * Verifies that [P2pKit.stop] actually calls cleanup on every registered
 * transport, and that a fresh kit constructed after `stop()` is independent
 * of the previous one.
 *
 * This guards against the class of bug seen in the v0.1 sample apps where the
 * UI's Stop button left the kit's mDNS/TCP listeners alive — that was a UI
 * lifecycle bug, but this test pins the library-side contract that the UI
 * fix relies on.
 */
class KitLifecycleTest {

    @Test
    fun stopClosesDataTransportAndStopsDiscoveryAdvertising() {
        runBlocking {
            val transport = TrackingTransport()
            val kit = P2pKit.create {
                appId = AppId("lifecycle-test")
                deviceName = "Test"
                transports { register(TrackingFactory(transport)) }
            }

            kit.startAdvertising()
            kit.startDiscovery()
            assertTrue(transport.advertisingStarted, "startAdvertising never propagated to transport")
            assertTrue(transport.discoveryStarted, "startDiscovery never propagated to transport")

            kit.stop()

            assertEquals(P2pState.Stopped, kit.state.value)
            assertTrue(transport.dataClosed, "DataTransport.close() should have been called")
            assertTrue(transport.advertisingStopped, "stopAdvertising should have been called")
            assertTrue(transport.discoveryStopped, "stopDiscovery should have been called")
        }
    }

    @Test
    fun freshKitAfterStopIsIndependent() {
        runBlocking {
            val first = TrackingTransport()
            val k1 = P2pKit.create {
                appId = AppId("indep-test")
                deviceName = "First"
                transports { register(TrackingFactory(first)) }
            }
            k1.startAdvertising()
            k1.stop()
            assertTrue(first.dataClosed)

            // After stopping the first kit, a brand-new kit with a separate
            // transport should not see any state leak from the first.
            val second = TrackingTransport()
            val k2 = P2pKit.create {
                appId = AppId("indep-test")
                deviceName = "Second"
                transports { register(TrackingFactory(second)) }
            }
            assertFalse(second.dataClosed, "Fresh transport should not be closed before any start")
            assertFalse(second.advertisingStarted, "Fresh transport should not have any advertising history")

            k2.startAdvertising()
            assertTrue(second.advertisingStarted)
            assertFalse(second.dataClosed)

            k2.stop()
            assertTrue(second.dataClosed)
        }
    }
}

/**
 * Single transport that implements both [DataTransport] and [DiscoveryTransport]
 * and records every lifecycle call as a `Boolean` so the test can assert on it.
 */
private class TrackingTransport : DataTransport, DiscoveryTransport {

    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100

    @Volatile var dataClosed: Boolean = false
    @Volatile var advertisingStarted: Boolean = false
    @Volatile var advertisingStopped: Boolean = false
    @Volatile var discoveryStarted: Boolean = false
    @Volatile var discoveryStopped: Boolean = false

    private val incomingChannel = Channel<RawConnection>(Channel.UNLIMITED)
    private val eventsFlow = MutableSharedFlow<PeerEvent>(extraBufferCapacity = 16)

    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection =
        error("TrackingTransport does not produce outgoing connections")

    override fun incomingConnections(): Flow<RawConnection> = incomingChannel.receiveAsFlow()

    override suspend fun close() {
        dataClosed = true
        incomingChannel.close()
    }

    override val events: Flow<PeerEvent> = eventsFlow.asSharedFlow()

    override suspend fun startAdvertising(localPeer: LocalPeerInfo) {
        advertisingStarted = true
    }

    override suspend fun stopAdvertising() {
        advertisingStopped = true
    }

    override suspend fun startDiscovery() {
        discoveryStarted = true
    }

    override suspend fun stopDiscovery() {
        discoveryStopped = true
    }
}

private class TrackingFactory(private val transport: TrackingTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = transport)
}
