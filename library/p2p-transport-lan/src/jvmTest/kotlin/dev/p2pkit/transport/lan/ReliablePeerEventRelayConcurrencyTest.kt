package dev.p2pkit.transport.lan

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import java.util.concurrent.CountDownLatch
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ReliablePeerEventRelayConcurrencyTest {
    @Test
    fun concurrentCallbackWritersCommitOneCoherentLiveSet() = runBlocking {
        val relay = ReliablePeerEventRelay()
        val start = CountDownLatch(1)
        val writers = (0 until PEER_COUNT).map { index ->
            async(Dispatchers.Default) {
                start.await()
                repeat(UPDATE_COUNT) { update ->
                    relay.upsert(peer(index, "version-$update"))
                }
                if (index % 2 != 0) relay.remove(PeerId(peerId(index)))
            }
        }

        start.countDown()
        writers.awaitAll()

        // Collection starts after every callback writer has completed. It
        // must replay exactly the even peers' latest values, with no mixed or
        // partially committed map and no dependency on callback ordering.
        val events = withTimeout(5_000) {
            relay.events.take(PEER_COUNT / 2).toList()
        }
        val found = events.map { assertIs<PeerEvent.Found>(it).peer }
        assertEquals(
            (0 until PEER_COUNT step 2).map(::peerId),
            found.map { it.publicPeer.id.value }
        )
        assertEquals(
            List(PEER_COUNT / 2) { "version-${UPDATE_COUNT - 1}" },
            found.map { it.publicPeer.name }
        )
    }

    @Test
    fun liveCollectorReconstructsConcurrentUpdatesAndReplacementLifecycles() = runBlocking {
        withTimeout(5_000) {
            val relay = ReliablePeerEventRelay()
            val removed = peer(0, "initial")
            val firstUpdated = peer(1, "initial")
            val firstReplaced = peer(2, "initial")
            val updated = peer(1, "changed")
            val replaced = peer(2, "replacement")
            val gate = peer(90, "initial-snapshot-gate")
            val tail = peer(99, "final-publication-witness")
            val seeds = listOf(removed, firstUpdated, firstReplaced, gate)
            seeds.forEach { assertTrue(relay.upsert(it)) }

            val initiallyObserved = CompletableDeferred<Unit>()
            val releaseInitial = CompletableDeferred<Unit>()
            val diffEntered = CompletableDeferred<Unit>()
            val concurrentWritesDone = CompletableDeferred<Unit>()
            val settled = CompletableDeferred<Pair<Map<PeerId, InternalPeer>, List<PeerEvent>>>()
            val watchedIds = setOf(removed.publicPeer.id, firstUpdated.publicPeer.id, firstReplaced.publicPeer.id)
            val writers = mutableListOf<Deferred<Unit>>()
            val collector = launch(Dispatchers.Default) {
                val live = linkedMapOf<PeerId, InternalPeer>()
                val watched = mutableListOf<PeerEvent>()
                relay.events.collect { event ->
                    val id = when (event) {
                        is PeerEvent.Found -> event.peer.publicPeer.id.also {
                            assertNull(live.put(it, event.peer), "Found requires an absent peer: $it")
                        }
                        is PeerEvent.Updated -> event.peer.publicPeer.id.also {
                            assertNotNull(live.put(it, event.peer), "Updated requires an observed peer: $it")
                        }
                        is PeerEvent.Lost -> event.peerId.also {
                            assertNotNull(live.remove(it), "Lost requires an observed peer: $it")
                        }
                    }
                    if (id in watchedIds) watched += event
                    if (event == PeerEvent.Found(gate)) {
                        assertEquals(seeds.associateBy { it.publicPeer.id }, live)
                        initiallyObserved.complete(Unit)
                        releaseInitial.await()
                    }
                    if (event == PeerEvent.Updated(updated)) {
                        // Real Default writers publish while this incremental diff is active.
                        diffEntered.complete(Unit)
                        concurrentWritesDone.await()
                    }
                    if (event == PeerEvent.Found(tail)) {
                        settled.complete(live.toMap() to watched.toList())
                    }
                }
            }
            try {
                initiallyObserved.await()
                val start = CompletableDeferred<Unit>()
                val mutations = listOf(
                    async(Dispatchers.Default) {
                        start.await()
                        relay.remove(removed.publicPeer.id)
                    },
                    async(Dispatchers.Default) {
                        start.await()
                        assertTrue(relay.upsert(updated))
                    },
                    async(Dispatchers.Default) {
                        start.await()
                        relay.remove(firstReplaced.publicPeer.id)
                        assertTrue(relay.upsert(replaced))
                    }
                )
                writers += mutations
                val noiseIndices = 3..10
                val noise = noiseIndices.map { index ->
                    async(Dispatchers.Default) {
                        diffEntered.await()
                        repeat(16) { version -> assertTrue(relay.upsert(peer(index, "version-$version"))) }
                        if (index % 2 != 0) relay.remove(PeerId(peerId(index)))
                    }
                }
                writers += noise
                start.complete(Unit)
                mutations.awaitAll()
                // Removal/re-add is necessarily conflated while the initial callback is parked.
                releaseInitial.complete(Unit)
                noise.awaitAll()
                concurrentWritesDone.complete(Unit)
                // Sorted last: this Found acknowledges the entire stable final snapshot, not a sleep.
                assertTrue(relay.upsert(tail))
                val (live, watched) = settled.await()
                val expected = listOf(updated, replaced, gate, tail) +
                    noiseIndices.filter { it % 2 == 0 }.map { peer(it, "version-15") }
                assertEquals(expected.associateBy { it.publicPeer.id }, live)
                assertEquals(
                    listOf(
                        PeerEvent.Found(removed), PeerEvent.Found(firstUpdated), PeerEvent.Found(firstReplaced),
                        PeerEvent.Lost(removed.publicPeer.id), PeerEvent.Updated(updated),
                        PeerEvent.Lost(firstReplaced.publicPeer.id), PeerEvent.Found(replaced)
                    ),
                    watched
                )
            } finally {
                releaseInitial.complete(Unit)
                concurrentWritesDone.complete(Unit)
                writers.forEach { it.cancel() }
                collector.cancelAndJoin()
            }
        }
    }

    private fun peer(index: Int, name: String): InternalPeer = InternalPeer(
        publicPeer = Peer(
            id = PeerId(peerId(index)),
            name = name,
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = emptyList()
    )

    private fun peerId(index: Int): String = "peer-${index.toString().padStart(2, '0')}"

    private companion object {
        const val PEER_COUNT: Int = 32
        const val UPDATE_COUNT: Int = 100
    }
}
