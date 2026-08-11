package dev.p2pkit.transport.lan

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import java.util.concurrent.CountDownLatch
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs

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
