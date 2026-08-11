package dev.p2pkit.transport.lan

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals

@OptIn(ExperimentalCoroutinesApi::class)
class ReliablePeerEventRelayTest {
    @Test
    fun lateCollectorReceivesCurrentPeersAsFoundInStableOrder() = runTest {
        val relay = ReliablePeerEventRelay()
        val peerB = peer("peer-b")
        val peerA = peer("peer-a")
        relay.upsert(peerB)
        relay.upsert(peerA)

        val events = relay.events.take(2).toList()

        assertEquals(
            listOf(PeerEvent.Found(peerA), PeerEvent.Found(peerB)),
            events
        )
    }

    @Test
    fun clearWithdrawsEveryObservedPeerInStableOrder() = runTest {
        val relay = ReliablePeerEventRelay()
        val peerB = peer("peer-b")
        val peerA = peer("peer-a")
        relay.upsert(peerB)
        relay.upsert(peerA)
        val result = async(start = CoroutineStart.UNDISPATCHED) {
            relay.events.take(4).toList()
        }

        runCurrent()
        relay.clear()
        runCurrent()

        assertEquals(
            listOf(
                PeerEvent.Found(peerA),
                PeerEvent.Found(peerB),
                PeerEvent.Lost(peerA.publicPeer.id),
                PeerEvent.Lost(peerB.publicPeer.id)
            ),
            result.await()
        )
    }

    @Test
    fun saturatedSlowCollectorStillReceivesLostForAnObservedPeer() = runTest {
        val relay = ReliablePeerEventRelay()
        val stable = peer("stable")
        val foundObserved = CompletableDeferred<Unit>()
        val releaseCollector = CompletableDeferred<Unit>()
        val result = async(start = CoroutineStart.UNDISPATCHED) {
            relay.events
                .onEach { event ->
                    if (event == PeerEvent.Found(stable)) {
                        foundObserved.complete(Unit)
                        releaseCollector.await()
                    }
                }
                .take(2)
                .toList()
        }

        relay.upsert(stable)
        runCurrent()
        foundObserved.await()

        // Far beyond the retired SharedFlow's 256-event capacity. All noise
        // is absent by the time the collector resumes; the live-set diff must
        // still withdraw the peer it had already observed.
        repeat(1_024) { index ->
            val noise = peer("noise-$index")
            relay.upsert(noise)
            relay.remove(noise.publicPeer.id)
        }
        relay.remove(stable.publicPeer.id)
        releaseCollector.complete(Unit)
        runCurrent()

        assertEquals(
            listOf(
                PeerEvent.Found(stable),
                PeerEvent.Lost(stable.publicPeer.id)
            ),
            result.await()
        )
    }

    @Test
    fun removeAndReaddCannotBeConflatedIntoOneContinuousLifecycle() = runTest {
        val relay = ReliablePeerEventRelay()
        val peer = peer("peer")
        val foundObserved = CompletableDeferred<Unit>()
        val releaseCollector = CompletableDeferred<Unit>()
        val result = async(start = CoroutineStart.UNDISPATCHED) {
            relay.events
                .onEach { event ->
                    if (event == PeerEvent.Found(peer) && !foundObserved.isCompleted) {
                        foundObserved.complete(Unit)
                        releaseCollector.await()
                    }
                }
                .take(3)
                .toList()
        }

        relay.upsert(peer)
        runCurrent()
        foundObserved.await()
        relay.remove(peer.publicPeer.id)
        relay.upsert(peer)
        releaseCollector.complete(Unit)
        runCurrent()

        assertEquals(
            listOf(
                PeerEvent.Found(peer),
                PeerEvent.Lost(peer.publicPeer.id),
                PeerEvent.Found(peer)
            ),
            result.await()
        )
    }

    @Test
    fun slowCollectorReceivesOnlyLatestInPlaceUpdate() = runTest {
        val relay = ReliablePeerEventRelay()
        val first = peer("peer", "first")
        val second = peer("peer", "second")
        val latest = peer("peer", "latest")
        val foundObserved = CompletableDeferred<Unit>()
        val releaseCollector = CompletableDeferred<Unit>()
        val result = async(start = CoroutineStart.UNDISPATCHED) {
            relay.events
                .onEach { event ->
                    if (event == PeerEvent.Found(first)) {
                        foundObserved.complete(Unit)
                        releaseCollector.await()
                    }
                }
                .take(2)
                .toList()
        }

        relay.upsert(first)
        runCurrent()
        foundObserved.await()
        relay.upsert(second)
        relay.upsert(latest)
        releaseCollector.complete(Unit)
        runCurrent()

        assertEquals(
            listOf(PeerEvent.Found(first), PeerEvent.Updated(latest)),
            result.await()
        )
    }

    @Test
    fun independentCollectorsEachReceiveTheCurrentSnapshot() = runTest {
        val relay = ReliablePeerEventRelay()
        val peer = peer("peer")
        relay.upsert(peer)

        val first = async { relay.events.take(1).toList() }
        val second = async { relay.events.take(1).toList() }

        assertEquals(listOf(PeerEvent.Found(peer)), first.await())
        assertEquals(listOf(PeerEvent.Found(peer)), second.await())
    }

    private fun peer(id: String, name: String = id): InternalPeer = InternalPeer(
        publicPeer = Peer(
            id = PeerId(id),
            name = name,
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = emptyList()
    )
}
