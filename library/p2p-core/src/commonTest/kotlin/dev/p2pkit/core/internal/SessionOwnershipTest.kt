package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.testfixtures.withTestKit
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.test.assertIs
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.yield

class SessionOwnershipTest {

    @Test
    fun cancelledDialFailsCoalescedWaiterRemovesPendingAndAllowsRetry() = runBlocking {
        val retryPair = FakeConnectionPair()
        val transport = FirstDialGateTransport(retryPair.a)
        withTestKit(
            create = { recorder ->
                kit("Alice", "alice-id", transport, recording = recorder)
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    kit(
                        "Bob",
                        "bob-id",
                        FakeDataTransport(preStagedIncoming = listOf(retryPair.b)),
                        recording = recorder
                    )
                }
            ) { bob ->
                alice.start()
                val incoming = async(start = CoroutineStart.UNDISPATCHED) {
                    withTimeout(5_000) { bob.incomingSessions.first() }
                }
                bob.start()

                val target = targetPeer()
                val connector = async { alice.connect(target) }
                transport.firstConnectEntered.await()
                val waiter = async(start = CoroutineStart.UNDISPATCHED) { alice.connect(target) }

                val cancellation = CancellationException("cancel connector during dial")
                connector.cancel(cancellation)
                val connectorFailure = assertFailsWith<CancellationException> { connector.await() }
                val waiterFailure = assertFailsWith<CancellationException> { waiter.await() }
                assertEquals(cancellation.message, connectorFailure.message)
                assertEquals(cancellation.message, waiterFailure.message)
                assertEquals(1, transport.connectCalls, "the second caller must coalesce")
                assertTrue(alice.sessions.value.isEmpty())

                val retried = withTimeout(5_000) { alice.connect(target) }
                assertEquals(ConnectionState.Connected, retried.state.value)
                assertSame(retried, withTimeout(5_000) { alice.connect(target) })
                assertEquals(ConnectionState.Connected, incoming.await().state.value)
                assertEquals(2, transport.connectCalls, "one cancelled dial plus one retry")
            }
        }
    }

    @OptIn(ExperimentalAtomicApi::class)
    @Test
    fun cancellationBeforeRegistrationClosesUncommittedSessionAndAllowsRetry() = runBlocking {
        val firstPair = FakeConnectionPair()
        val retryPair = FakeConnectionPair()
        val outgoing = ArrayDeque<RawConnection>().apply {
            add(firstPair.a)
            add(retryPair.a)
        }
        val commitEntered = CompletableDeferred<Unit>()
        var commitAttempts = 0
        val bobSetupsCompleted = AtomicInt(0)
        val bothBobSetupsCompleted = CompletableDeferred<Unit>()
        withTestKit(
            create = { recorder ->
                kit(
                    "Alice",
                    "alice-id",
                    FakeDataTransport(outgoingConnection = { outgoing.removeFirst() }),
                    beforeCommit = {
                        if (commitAttempts++ == 0) {
                            commitEntered.complete(Unit)
                            CompletableDeferred<Unit>().await()
                        }
                    },
                    recording = recorder
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    kit(
                        "Bob",
                        "bob-id",
                        FakeDataTransport(preStagedIncoming = listOf(firstPair.b, retryPair.b)),
                        afterResult = {
                            if (bobSetupsCompleted.addAndFetch(1) == 2) bothBobSetupsCompleted.complete(Unit)
                        },
                        recording = recorder
                    )
                }
            ) { bob ->
                alice.start()
                bob.start()
                val first = async { alice.connect(targetPeer()) }
                commitEntered.await()

                first.cancel(CancellationException("cancel before session commit"))
                val failure = assertFailsWith<CancellationException> { first.await() }
                assertEquals("cancel before session commit", failure.message)
                assertEquals(ConnectionState.Closed, firstPair.a.state.value)
                assertTrue(alice.sessions.value.isEmpty())

                val retried = withTimeout(5_000) { alice.connect(targetPeer()) }
                assertEquals(ConnectionState.Connected, retried.state.value)
                assertEquals(1, alice.sessions.value.size)

                // Preserve the immediate local retry above; only teardown waits for the two
                // controlled responder setups, so stop cannot race their session-commit gates.
                withTimeout(5_000) { bothBobSetupsCompleted.await() }
                assertEquals(2, bobSetupsCompleted.load())
            }
        }
    }

    @Test
    fun cancellationAfterDialOwnershipClosesRawAndAllowsRetry() = runBlocking {
        val firstPair = FakeConnectionPair()
        val retryPair = FakeConnectionPair()
        val outgoing = ArrayDeque<RawConnection>().apply {
            add(firstPair.a)
            add(retryPair.a)
        }
        val afterDialEntered = CompletableDeferred<Unit>()
        var hookCalls = 0
        val bobSetupCompleted = CompletableDeferred<Unit>()
        withTestKit(
            create = { recorder ->
                kit(
                    "Alice",
                    "alice-id",
                    FakeDataTransport(outgoingConnection = { outgoing.removeFirst() }),
                    afterDial = {
                        if (hookCalls++ == 0) {
                            afterDialEntered.complete(Unit)
                            CompletableDeferred<Unit>().await()
                        }
                    },
                    recording = recorder
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    kit(
                        "Bob",
                        "bob-id",
                        FakeDataTransport(preStagedIncoming = listOf(retryPair.b)),
                        afterResult = { bobSetupCompleted.complete(Unit) },
                        recording = recorder
                    )
                }
            ) { bob ->
                alice.start()
                bob.start()
                val first = async { alice.connect(targetPeer()) }
                afterDialEntered.await()

                first.cancel(CancellationException("cancel after dial ownership"))
                val failure = assertFailsWith<CancellationException> { first.await() }
                assertEquals("cancel after dial ownership", failure.message)
                assertEquals(ConnectionState.Closed, firstPair.a.state.value)
                assertTrue(alice.sessions.value.isEmpty())

                val retried = withTimeout(5_000) { alice.connect(targetPeer()) }
                assertEquals(ConnectionState.Connected, retried.state.value)
                assertEquals(1, alice.sessions.value.size)

                // The retry's local result does not join the responder's commit.
                withTimeout(5_000) { bobSetupCompleted.await() }
            }
        }
    }

    @OptIn(ExperimentalAtomicApi::class)
    @Test
    fun cancellationAfterCommittedSetupResultRollsBackSessionAndAllowsRetry() = runBlocking {
        val firstPair = FakeConnectionPair()
        val retryPair = FakeConnectionPair()
        val outgoing = ArrayDeque<RawConnection>().apply {
            add(firstPair.a)
            add(retryPair.a)
        }
        val resultProduced = CompletableDeferred<Unit>()
        var hookCalls = 0
        val bobSetupsCompleted = AtomicInt(0)
        val bothBobSetupsCompleted = CompletableDeferred<Unit>()
        withTestKit(
            create = { recorder ->
                kit(
                    "Alice",
                    "alice-id",
                    FakeDataTransport(outgoingConnection = { outgoing.removeFirst() }),
                    afterResult = {
                        if (hookCalls++ == 0) {
                            resultProduced.complete(Unit)
                            CompletableDeferred<Unit>().await()
                        }
                    },
                    recording = recorder
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    kit(
                        "Bob",
                        "bob-id",
                        FakeDataTransport(preStagedIncoming = listOf(firstPair.b, retryPair.b)),
                        afterResult = {
                            if (bobSetupsCompleted.addAndFetch(1) == 2) bothBobSetupsCompleted.complete(Unit)
                        },
                        recording = recorder
                    )
                }
            ) { bob ->
                alice.start()
                bob.start()
                val first = async { alice.connect(targetPeer()) }
                resultProduced.await()
                val committed = alice.sessions.value.single()

                first.cancel(CancellationException("cancel committed result handoff"))
                val failure = assertFailsWith<CancellationException> { first.await() }
                assertEquals("cancel committed result handoff", failure.message)
                assertEquals(ConnectionState.Closed, committed.state.value)
                assertEquals(ConnectionState.Closed, firstPair.a.state.value)
                assertTrue(alice.sessions.value.isEmpty())

                val retried = withTimeout(5_000) { alice.connect(targetPeer()) }
                assertEquals(ConnectionState.Connected, retried.state.value)
                assertEquals(1, alice.sessions.value.size)

                // Keep cancellation and retry immediate; join both responder setups only for teardown.
                withTimeout(5_000) { bothBobSetupsCompleted.await() }
                assertEquals(2, bobSetupsCompleted.load())
            }
        }
    }

    @Test
    fun stopAfterCommittedSetupResultNeverReturnsTheClosedSession() = runBlocking {
        val pair = FakeConnectionPair()
        val resultProduced = CompletableDeferred<Unit>()
        val releaseDelivery = CompletableDeferred<Unit>()
        val bobSetupCompleted = CompletableDeferred<Unit>()
        withTestKit(
            create = { recorder ->
                kit(
                    "Alice",
                    "alice-id",
                    FakeDataTransport(outgoingConnection = { pair.a }),
                    afterResult = {
                        resultProduced.complete(Unit)
                        releaseDelivery.await()
                    },
                    recording = recorder
                )
            }
        ) { alice ->
            withTestKit(
                create = { recorder ->
                    kit(
                        "Bob",
                        "bob-id",
                        FakeDataTransport(preStagedIncoming = listOf(pair.b)),
                        afterResult = { bobSetupCompleted.complete(Unit) },
                        recording = recorder
                    )
                }
            ) { bob ->
                try {
                    alice.start()
                    bob.start()
                    val connector = async { runCatching { alice.connect(targetPeer()) } }
                    resultProduced.await()
                    val committed = alice.sessions.value.single()

                    alice.stop()
                    assertEquals(ConnectionState.Closed, committed.state.value)
                    assertTrue(alice.sessions.value.isEmpty())

                    releaseDelivery.complete(Unit)
                    val failure = connector.await().exceptionOrNull()
                    assertTrue(failure is IllegalStateException)
                    assertTrue(failure.message.orEmpty().contains("stopped"))

                    // Alice's controlled stop stays unchanged; Bob must finish before its own stop.
                    withTimeout(5_000) { bobSetupCompleted.await() }
                } finally {
                    releaseDelivery.complete(Unit)
                }
            }
        }
    }

    @Test
    fun inboundSetupDeadlineClosesIdleRawReleasesAdmissionAndAcceptsNextPeer() = runBlocking {
        val idlePair = FakeConnectionPair()
        val successPair = FakeConnectionPair()
        val bobTransport = FakeDataTransport(preStagedIncoming = listOf(idlePair.b))
        lateinit var timeoutDiagnostics: RecordingLogger
        withTestKit(
            create = { recorder ->
                timeoutDiagnostics = recorder
                kit(
                    "Bob",
                    "bob-id",
                    bobTransport,
                    setupTimeoutMillis = 100,
                    recording = recorder
                )
            },
            verifyDiagnostics = { recorder ->
                val diagnostics = recorder.entries.filter {
                    it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
                }
                assertEquals(1, diagnostics.size)
                val entry = diagnostics.single()
                assertEquals(RecordingLogger.Level.WARN, entry.level)
                assertEquals("Incoming session setup failed", entry.message)
                val failure = assertIs<P2pError.HandshakeRejected>(entry.throwable)
                // Both nested deadlines are 100ms; the outer full-setup deadline normally wins.
                assertTrue(failure.reason in setOf(
                    "Plaintext HELLO timed out after 100 ms",
                    "Handshake timed out after 100 ms"
                ))
                assertTrue(failure.suppressedExceptions.isEmpty())
            }
        ) { bob ->
            bob.start()
            assertEquals(
                ConnectionState.Closed,
                withTimeout(5_000) { idlePair.b.state.first { it == ConnectionState.Closed } }
            )
            assertTrue(bob.sessions.value.isEmpty())
            // Join the expected setup failure at its logger publication before stopping the kit.
            // Otherwise stop could cancel the failed setup after raw close but before its catch logs.
            withTimeout(5_000) {
                while (timeoutDiagnostics.entries.none { it.message == "Incoming session setup failed" }) yield()
            }

            val incoming = async(start = CoroutineStart.UNDISPATCHED) {
                withTimeout(5_000) { bob.incomingSessions.first() }
            }
            // Pre-buffer the remote HELLO before handing the connection to
            // Bob. The 100 ms setup deadline is intentionally kept strict to
            // prove idle setup expiry; making the valid follow-up depend on a
            // second kit's concurrently scheduled handshake made this test
            // nondeterministic on loaded native CI runners. A buffered valid
            // frame still exercises the same recovered admission permit and
            // complete inbound setup path without weakening that deadline.
            DefaultP2pProtocol(clock = { 0L }).sendHello(
                successPair.a,
                HelloPayload(
                    appId = "session-ownership-test",
                    peerId = "alice-id",
                    deviceName = "Alice",
                    platform = Platform.JVM_DESKTOP.name,
                    supportedTransports = listOf(TransportKind.LAN.name)
                )
            )
            bobTransport.emitIncoming(successPair.b)
            val admitted = incoming.await()
            assertEquals(PeerId("alice-id"), admitted.peer.id)
            assertEquals(ConnectionState.Connected, admitted.state.value)
        }
    }

    private fun kit(
        name: String,
        id: String,
        transport: DataTransport,
        beforeCommit: (suspend () -> Unit)? = null,
        afterDial: (suspend () -> Unit)? = null,
        afterResult: (suspend () -> Unit)? = null,
        setupTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MS,
        recording: P2pLogger
    ): P2pKit = createTestKit {
        logger = recording
        appId = AppId("session-ownership-test")
        deviceName = name
        peerIdStorage = InMemoryPeerIdStorage(PeerId(id))
        beforeSessionCommitForTest = beforeCommit
        afterOutgoingConnectForTest = afterDial
        afterSessionSetupResultForTest = afterResult
        sessionSetupTimeoutMillis = setupTimeoutMillis
        keepAlive {
            pingIntervalMillis = 60_000
            timeoutMillis = 120_000
        }
        transports { register(OwnershipFactory(transport)) }
    }

    private fun targetPeer(): Peer = Peer(
        id = PeerId("bob-id"),
        name = "Bob",
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )
}

private class FirstDialGateTransport(
    private val retryConnection: RawConnection
) : DataTransport {
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100
    val firstConnectEntered = CompletableDeferred<Unit>()
    var connectCalls: Int = 0
        private set

    override suspend fun start(): Result<Unit> = Result.success(Unit)
    override fun canConnect(peer: InternalPeer): Boolean = true
    override suspend fun connect(peer: InternalPeer): RawConnection {
        connectCalls++
        if (connectCalls == 1) {
            firstConnectEntered.complete(Unit)
            CompletableDeferred<Unit>().await()
        }
        return retryConnection
    }
    // This dial-gating fixture models an open, idle accept source, not a crashed accept loop.
    override fun incomingConnections(): Flow<RawConnection> = flow { awaitCancellation() }
    override suspend fun stop() = Unit
    override suspend fun close() = Unit
}

private class OwnershipFactory(private val transport: DataTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair = TransportPair(transport)
}
