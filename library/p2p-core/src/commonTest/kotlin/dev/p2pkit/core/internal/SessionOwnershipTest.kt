package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

class SessionOwnershipTest {

    @Test
    fun cancelledDialFailsCoalescedWaiterRemovesPendingAndAllowsRetry() = runBlocking {
        val retryPair = FakeConnectionPair()
        val transport = FirstDialGateTransport(retryPair.a)
        val alice = kit("Alice", "alice-id", transport)
        val bob = kit(
            "Bob",
            "bob-id",
            FakeDataTransport(preStagedIncoming = listOf(retryPair.b))
        )
        try {
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
        } finally {
            alice.stop()
            bob.stop()
        }
    }

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
        val alice = kit(
            "Alice",
            "alice-id",
            FakeDataTransport(outgoingConnection = { outgoing.removeFirst() }),
            beforeCommit = {
                if (commitAttempts++ == 0) {
                    commitEntered.complete(Unit)
                    CompletableDeferred<Unit>().await()
                }
            }
        )
        val bob = kit(
            "Bob",
            "bob-id",
            FakeDataTransport(preStagedIncoming = listOf(firstPair.b, retryPair.b))
        )
        try {
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
        } finally {
            alice.stop()
            bob.stop()
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
        val alice = kit(
            "Alice",
            "alice-id",
            FakeDataTransport(outgoingConnection = { outgoing.removeFirst() }),
            afterDial = {
                if (hookCalls++ == 0) {
                    afterDialEntered.complete(Unit)
                    CompletableDeferred<Unit>().await()
                }
            }
        )
        val bob = kit(
            "Bob",
            "bob-id",
            FakeDataTransport(preStagedIncoming = listOf(retryPair.b))
        )
        try {
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
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun inboundSetupDeadlineClosesIdleRawReleasesAdmissionAndAcceptsNextPeer() = runBlocking {
        val idlePair = FakeConnectionPair()
        val successPair = FakeConnectionPair()
        val bobTransport = FakeDataTransport(preStagedIncoming = listOf(idlePair.b))
        val bob = kit(
            "Bob",
            "bob-id",
            bobTransport,
            setupTimeoutMillis = 100
        )
        try {
            bob.start()
            assertEquals(
                ConnectionState.Closed,
                withTimeout(5_000) { idlePair.b.state.first { it == ConnectionState.Closed } }
            )
            assertTrue(bob.sessions.value.isEmpty())

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
        } finally {
            bob.stop()
        }
    }

    private fun kit(
        name: String,
        id: String,
        transport: DataTransport,
        beforeCommit: (suspend () -> Unit)? = null,
        afterDial: (suspend () -> Unit)? = null,
        setupTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MS
    ): P2pKit = createTestKit {
        appId = AppId("session-ownership-test")
        deviceName = name
        peerIdStorage = InMemoryPeerIdStorage(PeerId(id))
        beforeSessionCommitForTest = beforeCommit
        afterOutgoingConnectForTest = afterDial
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
    override fun incomingConnections(): Flow<RawConnection> = emptyFlow()
    override suspend fun stop() = Unit
    override suspend fun close() = Unit
}

private class OwnershipFactory(private val transport: DataTransport) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(transport.type)
    override fun build(context: TransportContext): TransportPair = TransportPair(transport)
}
