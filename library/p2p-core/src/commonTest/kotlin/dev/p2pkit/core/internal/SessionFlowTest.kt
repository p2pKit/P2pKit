package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.testfixtures.runWireBlocking
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.Frame
import dev.p2pkit.core.protocol.FrameCodec
import dev.p2pkit.core.protocol.FrameFlags
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.protocol.PacketType
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.onSubscription
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
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

    private fun outgoingKit(
        name: String,
        outgoing: RawConnection,
        recording: P2pLogger
    ): P2pKit =
        createTestKit {
            logger = recording
            appId = AppId("com.example.test")
            deviceName = name
            // Keep the simulated peers hermetic across JVM and iOS runners;
            // default storage is intentionally persistent production state.
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("alice-id"))
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            transports {
                register(FactoryFor(FakeDataTransport(outgoingConnection = { outgoing })))
            }
        }

    private fun incomingKit(
        name: String,
        incoming: RawConnection,
        recording: P2pLogger
    ): P2pKit =
        createTestKit {
            logger = recording
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

    private suspend fun withSessionKits(
        pair: FakeConnectionPair,
        test: suspend (P2pKit, P2pKit) -> Unit
    ) {
        withTestKit(create = { outgoingKit("Alice", pair.a, recording = it) }) { alice ->
            withTestKit(create = { incomingKit("Bob", pair.b, recording = it) }) { bob ->
                test(alice, bob)
            }
        }
    }

    @Test
    fun outgoingSessionExchangesText() = runWireBlocking { delivery ->
        val pair = FakeConnectionPair(delivery)
        withSessionKits(pair) { alice, bob ->
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
        }
    }

    @Test
    fun outgoingSessionExchangesBinary() = runWireBlocking { delivery ->
        val pair = FakeConnectionPair(delivery)
        withSessionKits(pair) { alice, bob ->
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
        }
    }

    @Test
    fun concurrentConnectCallsForSamePeerReturnTheSameSession() = runBlocking {
        val pair = FakeConnectionPair()
        withSessionKits(pair) { alice, _ ->
            val target = syntheticPeer("bob-id", "Bob")
            // Two coroutines try to connect simultaneously. With the per-peer
            // mutex, the second one must observe the first as in-flight and
            // await it — returning the same session, not creating a duplicate.
            val first = async { alice.connect(target) }
            val second = async { alice.connect(target) }
            val s1 = withTimeout(5_000) { first.await() }
            val s2 = withTimeout(5_000) { second.await() }
            assertSame(s1, s2, "Concurrent connect() to the same peer must return the same session")
        }
    }

    @Test
    fun connectIsIdempotentForSamePeer() = runBlocking {
        val pair = FakeConnectionPair()
        withSessionKits(pair) { alice, _ ->
            val target = syntheticPeer("bob-id", "Bob")
            val first = withTimeout(5_000) { alice.connect(target) }
            // SessionManager's `active` map is updated synchronously inside
            // connect(), so the second call should short-circuit to `first`.
            val second = withTimeout(5_000) { alice.connect(target) }
            assertSame(first, second, "connect() should return the same active session")
        }
    }

    @Test
    fun concurrentSendsDoNotInterleave() = runWireBlocking { delivery ->
        val pair = FakeConnectionPair(delivery)
        withSessionKits(pair) { alice, bob ->
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
        }
    }

    @Test
    fun closeTransitionsSessionToClosed() = runWireBlocking { delivery ->
        val pair = FakeConnectionPair(delivery)
        withSessionKits(pair) { alice, bob ->
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
            val incomingImpl = assertIs<P2pSessionImpl>(incomingSession)
            withTimeout(5_000) { incomingImpl.awaitRuntimeTermination() }
            assertTrue(
                !incomingImpl.runtimeJobIsActiveForTest,
                "remote CLOSE must terminate the session-wide runtime job"
            )
        }
    }

    @Test
    fun incomingSessionFailsDeterministicallyOnAbruptRemoteTermination() = runWireBlocking { delivery ->
        // AUDIT-2026-07 (SES-1) / P1-01: an incoming session whose wire ends
        // WITHOUT a CLOSE frame (EOF/reset signature — the peer's process went
        // away) must deterministically reach Failed: incoming sessions never
        // reconnect (the remote redials) and a hangup without CLOSE is not a
        // clean close, so the clean-Closed outcome must never appear.
        val pair = FakeConnectionPair(delivery)
        withTestKit(
            create = { recorder ->
                outgoingKit("Alice", pair.a, recording = recorder)
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", pair.b, recording = recorder)
                }
            ) { bob ->
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
                val incomingImpl = assertIs<P2pSessionImpl>(incomingSession)
                withTimeout(5_000) { incomingImpl.awaitRuntimeTermination() }
                assertTrue(
                    !incomingImpl.runtimeJobIsActiveForTest,
                    "remote failure must terminate the session-wide runtime job"
                )
            }
        }
    }

    @Test
    fun eofDuringPartialFrameFailsSessionWithoutPublishingAMessage() = runWireBlocking { delivery ->
        val pair = FakeConnectionPair(delivery)
        withTestKit(
            create = { recorder ->
                outgoingKit("Alice", pair.a, recording = recorder)
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", pair.b, recording = recorder)
                }
            ) { bob ->
                val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
                val incoming = withTimeout(5_000) { bob.incomingSessions.first() }
                withTimeout(5_000) { outgoingDeferred.await() }
                val subscribed = CompletableDeferred<Unit>()
                val messages = mutableListOf<P2pMessage>()
                val collector = launch {
                    incoming.incoming.onSubscription { subscribed.complete(Unit) }.collect { messages += it }
                }
                try {
                    subscribed.await()
                    val frame = FrameCodec.encode(
                        Frame(
                            type = PacketType.DATA,
                            flags = FrameFlags.LAST_CHUNK.toByte(),
                            messageId = MessageId(ByteArray(MessageId.SIZE) { it.toByte() }),
                            chunkIndex = 0,
                            totalChunks = 1,
                            payload = ByteArray(2_048) { it.toByte() }
                        )
                    )
                    pair.a.write(frame.copyOf(frame.size - 17))
                    pair.hangUp(pair.a)
                    val terminal = withTimeout(5_000) { incoming.state.first { it != ConnectionState.Connected } }
                    assertEquals(ConnectionState.Failed, terminal)
                    val implementation = assertIs<P2pSessionImpl>(incoming)
                    withTimeout(5_000) { implementation.awaitRuntimeTermination() }
                    assertTrue(!implementation.runtimeJobIsActiveForTest)
                    assertTrue(messages.isEmpty(), "a partial frame must never be exposed as an application message")
                } finally {
                    collector.cancelAndJoin()
                }
            }
        }
    }

    @Test
    fun failedPongWriteFailsIncomingSessionInsteadOfSilentlyContinuing() = runBlocking {
        val pair = FakeConnectionPair()
        val pongFailure = IllegalStateException("injected PONG write failure")
        var expectedDiagnostic: RecordingLogger.Entry? = null
        withTestKit(
            create = { recorder ->
                outgoingKit("Alice", pair.a, recording = recorder)
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKit("Bob", pair.b, recording = recorder)
                },
                verifyDiagnostics = { recorder ->
                    val expected = expectedDiagnostic
                    recorder.assertNoUnexpectedWarnOrError { it == expected }
                    if (expected != null) assertEquals(1, recorder.entries.count { it == expected })
                }
            ) { bob ->
                val outgoingDeferred = async { alice.connect(syntheticPeer("bob-id", "Bob")) }
                val incomingSession = withTimeout(5_000) { bob.incomingSessions.first() }
                withTimeout(5_000) { outgoingDeferred.await() }

                expectedDiagnostic = RecordingLogger.Entry(
                    RecordingLogger.Level.WARN,
                    "Session ${incomingSession.id}: failed to send PONG",
                    pongFailure
                )
                pair.b.failNextWrite(pongFailure)
                DefaultP2pProtocol(clock = { 0L }).sendPing(pair.a)

                assertEquals(
                    ConnectionState.Failed,
                    withTimeout(5_000) {
                        incomingSession.state.first { it == ConnectionState.Failed }
                    }
                )
                val implementation = assertIs<P2pSessionImpl>(incomingSession)
                withTimeout(5_000) { implementation.awaitRuntimeTermination() }
                assertTrue(!implementation.runtimeJobIsActiveForTest)
            }
        }
    }

    @Test
    fun cancelledConnectorReleasesPendingAndRawThenRetrySucceeds() = runBlocking {
        val appId = AppId("cancelled-connector-retry")
        val blockedPair = FakeConnectionPair()
        val blocked = CancellableFirstWriteConnection(blockedPair.a)
        val retryPair = FakeConnectionPair()
        val outgoing = ArrayDeque<RawConnection>().apply {
            add(blocked)
            add(retryPair.a)
        }
        val transport = FakeDataTransport(outgoingConnection = {
            outgoing.removeFirstOrNull() ?: error("unexpected extra dial")
        })
        withTestKit(create = { recorder ->
            createTestKit {
                logger = recorder
                this.appId = appId
                deviceName = "Alice"
                peerIdStorage = InMemoryPeerIdStorage(PeerId("alice-id"))
                transports { register(FactoryFor(transport)) }
            }
        }) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKitWithConnections(appId, listOf(retryPair.b), recording = recorder)
                }
            ) { bob ->
                val target = syntheticPeer("bob-id", "Bob")
                alice.start()
                bob.start()
                val connector = async { alice.connect(target) }
                withTimeout(5_000) { blocked.writeEntered.await() }

                // With an already-started kit, UNDISPATCHED reaches the shared
                // pending deferred before returning to this coroutine.
                val waiter = async(start = CoroutineStart.UNDISPATCHED) { alice.connect(target) }
                assertEquals(1, transport.connectCalls.size)

                connector.cancel(CancellationException("cancel connector"))
                val connectorFailure = assertFailsWith<CancellationException> { connector.await() }
                val waiterFailure = assertFailsWith<CancellationException> { waiter.await() }
                assertEquals("cancel connector", connectorFailure.message)
                assertEquals("cancel connector", waiterFailure.message)
                assertEquals(1, blocked.closeCalls)
                assertEquals(ConnectionState.Closed, blocked.state.value)
                assertTrue(alice.sessions.value.isEmpty())

                val retried = withTimeout(5_000) { alice.connect(target) }
                assertEquals(ConnectionState.Connected, retried.state.value)
                assertEquals(2, transport.connectCalls.size)
                assertEquals(listOf(retried), alice.sessions.value)
            }
        }
    }

    @Test
    fun wholeSetupDeadlineClosesStalledRawAndRetrySucceeds() = runBlocking {
        val appId = AppId("whole-setup-deadline")
        val stalled = SetupStalledConnection()
        val retryPair = FakeConnectionPair()
        val outgoing = ArrayDeque<RawConnection>().apply {
            add(stalled)
            add(retryPair.a)
        }
        val transport = FakeDataTransport(outgoingConnection = {
            outgoing.removeFirstOrNull() ?: error("unexpected extra dial")
        })
        withTestKit(create = { recorder ->
            createTestKit {
                logger = recorder
                this.appId = appId
                deviceName = "Alice"
                peerIdStorage = InMemoryPeerIdStorage(PeerId("alice-id"))
                sessionSetupTimeoutMillis = 100
                transports { register(FactoryFor(transport)) }
            }
        }) { alice ->
            withTestKit(
                create = { recorder ->
                    incomingKitWithConnections(appId, listOf(retryPair.b), recording = recorder)
                }
            ) { bob ->
                val target = syntheticPeer("bob-id", "Bob")
                bob.start()
                assertFailsWith<dev.p2pkit.core.P2pError.HandshakeRejected> {
                    withTimeout(5_000) { alice.connect(target) }
                }
                assertEquals(ConnectionState.Closed, stalled.state.value)
                assertEquals(1, stalled.closeCalls)
                assertTrue(alice.sessions.value.isEmpty())

                val retried = withTimeout(5_000) { alice.connect(target) }
                assertEquals(ConnectionState.Connected, retried.state.value)
                assertEquals(2, transport.connectCalls.size)
            }
        }
    }

    private fun incomingKitWithConnections(
        appId: AppId,
        incoming: List<RawConnection>,
        recording: P2pLogger
    ): P2pKit = createTestKit {
        logger = recording
        this.appId = appId
        deviceName = "Bob"
        peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports {
            register(FactoryFor(FakeDataTransport(preStagedIncoming = incoming)))
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

@OptIn(ExperimentalAtomicApi::class)
private class CancellableFirstWriteConnection(
    private val delegate: RawConnection
) : RawConnection {
    val writeEntered = CompletableDeferred<Unit>()
    private val release = CompletableDeferred<Unit>()
    private val closeCounter = AtomicInt(0)
    val closeCalls: Int get() = closeCounter.load()
    override val state: StateFlow<ConnectionState> get() = delegate.state

    override suspend fun write(bytes: ByteArray) {
        writeEntered.complete(Unit)
        release.await()
        delegate.write(bytes)
    }

    override fun read(): Flow<ByteArray> = delegate.read()

    override suspend fun close() {
        closeCounter.addAndFetch(1)
        release.complete(Unit)
        delegate.close()
    }
}

@OptIn(ExperimentalAtomicApi::class)
private class SetupStalledConnection : RawConnection {
    private val _state = MutableStateFlow(ConnectionState.Connected)
    private val closeCounter = AtomicInt(0)
    val closeCalls: Int get() = closeCounter.load()
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    override suspend fun write(bytes: ByteArray): Unit = awaitCancellation()

    override fun read(): Flow<ByteArray> = flow { awaitCancellation() }

    override suspend fun close() {
        closeCounter.addAndFetch(1)
        _state.value = ConnectionState.Closed
    }
}

private class FactoryFor(private val transport: FakeDataTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair =
        TransportPair(data = transport, discovery = null)
}
