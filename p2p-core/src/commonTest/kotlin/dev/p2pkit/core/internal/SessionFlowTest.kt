package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

/**
 * End-to-end-ish tests that wire up two [P2pKit] instances against a single
 * shared [FakeConnectionPair] and verify the full
 * outgoing-handshake → message → close flow.
 *
 * Note: [P2pSession.incoming] is `replay = 0` per the spec, so tests must
 * ensure the subscriber is attached *before* the producer side calls `send`.
 * The [firstMessageAfterSubscription] helper does that with `onSubscription`.
 */
class SessionFlowTest {

    private fun outgoingKit(name: String, outgoing: RawConnection): P2pKit =
        P2pKit.create {
            appId = AppId("com.example.test")
            deviceName = name
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            transports {
                register(FactoryFor(FakeDataTransport(outgoingConnection = { outgoing })))
            }
        }

    private fun incomingKit(name: String, incoming: RawConnection): P2pKit =
        P2pKit.create {
            appId = AppId("com.example.test")
            deviceName = name
            // Seed the incoming peer's id to the value the outgoing side dials
            // ("bob-id") so the HELLO peerId matches — mirrors production, where
            // the dialed id comes from the same discovery record the peer
            // advertises. Required since the outgoing handshake now verifies it.
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            transports {
                register(FactoryFor(FakeDataTransport(preStagedIncoming = listOf(incoming))))
            }
        }

    @Test
    fun outgoingSessionExchangesText() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            assertEquals("Alice", incomingSession.peer.name)
            assertEquals("Bob", outgoing.peer.name)

            val msg = exchangeMessage(
                scope = this,
                from = outgoing,
                to = incomingSession,
                payload = P2pMessage.Text("hello from Alice")
            )
            val text = assertIs<P2pMessage.Text>(msg)
            assertEquals("hello from Alice", text.value)
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun outgoingSessionExchangesBinary() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            val payload = ByteArray(4096) { it.toByte() }
            val msg = exchangeMessage(
                scope = this,
                from = incomingSession,
                to = outgoing,
                payload = P2pMessage.Binary(payload)
            )
            val bin = assertIs<P2pMessage.Binary>(msg)
            assertContentEquals(payload, bin.bytes)
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun concurrentConnectCallsForSamePeerReturnTheSameSession() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val target = syntheticPeer("bob-id", "Bob")
            // Two coroutines try to connect simultaneously. With the per-peer
            // mutex, the second one must observe the first as in-flight and
            // await it — returning the same session, not creating a duplicate.
            val first = async { alice.connect(target) }
            val second = async { alice.connect(target) }
            val s1 = withTimeout(5_000) { first.await() }
            val s2 = withTimeout(5_000) { second.await() }
            assertSame(s1, s2, "Concurrent connect() to the same peer must return the same session")
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun connectIsIdempotentForSamePeer() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val target = syntheticPeer("bob-id", "Bob")
            val first = withTimeout(5_000) { alice.connect(target) }
            // SessionManager's `active` map is updated synchronously inside
            // connect(), so the second call should short-circuit to `first`.
            val second = withTimeout(5_000) { alice.connect(target) }
            assertSame(first, second, "connect() should return the same active session")
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun concurrentSendsDoNotInterleave() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            val ready = CompletableDeferred<Unit>()
            val received = mutableListOf<P2pMessage>()
            val done = CompletableDeferred<Unit>()
            val collectJob = launch {
                incomingSession.incoming
                    .onSubscription { ready.complete(Unit) }
                    .collect {
                        received.add(it)
                        if (received.size == 5) done.complete(Unit)
                    }
            }
            ready.await()

            launch { outgoing.send(P2pMessage.Text("aaaa")) }
            launch { outgoing.send(P2pMessage.Text("bbbbbbbb")) }
            launch { outgoing.send(P2pMessage.Binary(ByteArray(2000) { 1 })) }
            launch { outgoing.send(P2pMessage.Text("dddd")) }
            launch { outgoing.send(P2pMessage.Binary(ByteArray(3000) { 2 })) }

            withTimeout(10_000) { done.await() }
            collectJob.cancel()

            assertEquals(5, received.size)
            val binaries = received.filterIsInstance<P2pMessage.Binary>()
            assertEquals(2, binaries.size)
            for (b in binaries) {
                val firstByte = b.bytes[0]
                assertTrue(b.bytes.all { it == firstByte }, "Frames interleaved within a message")
            }
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun closeTransitionsSessionToClosed() = runBlocking {
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            val outgoing = withTimeout(5_000) { outgoingDeferred.await() }

            outgoing.close()
            assertEquals(ConnectionState.Closed, outgoing.state.value)
            val finalState = withTimeout(5_000) {
                incomingSession.state.first {
                    it == ConnectionState.Closed || it == ConnectionState.Failed
                }
            }
            // AUDIT-2026-07 (SES-1) / P1-02: the peer that receives our CLOSE
            // frame must classify it as a clean close — exactly Closed, never
            // Failed. (Was the disjunctive `Closed || Failed` while the
            // remote-termination classification raced.)
            assertEquals(
                ConnectionState.Closed, finalState,
                "a received CLOSE frame must yield exactly Closed on the receiving side"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun incomingSessionFailsDeterministicallyOnAbruptRemoteTermination() = runBlocking {
        // AUDIT-2026-07 (SES-1) / P1-01: an incoming session whose wire ends
        // WITHOUT a CLOSE frame (EOF/reset signature — the peer's process went
        // away) must deterministically reach Failed: incoming sessions never
        // reconnect (the remote redials) and a hangup without CLOSE is not a
        // clean close, so the clean-Closed outcome must never appear.
        val pair = FakeConnectionPair()
        val alice = outgoingKit("Alice", pair.a)
        val bob = incomingKit("Bob", pair.b)
        try {
            val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
            val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
            withTimeout(5_000) { outgoingDeferred.await() }
            assertEquals(ConnectionState.Connected, incomingSession.state.value)

            // Subscribe to the FIRST transition out of Connected before
            // inducing the loss, so the edge cannot be missed (UNDISPATCHED
            // runs the collector up to its first suspension point right here).
            val firstTransition = async(start = CoroutineStart.UNDISPATCHED) {
                incomingSession.state.first { it != ConnectionState.Connected }
            }

            // Production-shaped remote termination (fixture F1): Alice's end
            // of the wire goes away with no CLOSE frame.
            pair.hangUp(pair.a)

            assertEquals(
                ConnectionState.Failed,
                withTimeout(5_000) { firstTransition.await() },
                "an incoming session must deterministically reach Failed on abrupt remote " +
                    "termination — never the clean-Closed outcome, never Reconnecting"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    /**
     * Subscribe on [to], wait for the subscription to register, then send
     * [payload] from [from]. Returns the first received message.
     *
     * Necessary because [P2pSession.incoming] does not buffer pre-subscription
     * messages.
     */
    private suspend fun exchangeMessage(
        scope: CoroutineScope,
        from: P2pSession,
        to: P2pSession,
        payload: P2pMessage
    ): P2pMessage {
        val ready = CompletableDeferred<Unit>()
        val received = scope.async {
            to.incoming.onSubscription { ready.complete(Unit) }.first()
        }
        ready.await()
        from.send(payload)
        return withTimeout(5_000) { received.await() }
    }

    private fun syntheticPeer(id: String, name: String): Peer = Peer(
        id = PeerId(id),
        name = name,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )
}

private class FactoryFor(private val transport: FakeDataTransport) : TransportFactory {
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
