package dev.p2pkit.rpc.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.Platform
import dev.p2pkit.core.SessionConnectionInfo
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

private class LinkTestSession : P2pSession {
    override val id = "rpc-test-session"
    override val peer = Peer(PeerId("rpc-peer"), "fixture", Platform.UNKNOWN, setOf(TransportKind.LAN))
    override val peerIdentity = PeerIdentity(peer.id, testFingerprint())
    override val state = MutableStateFlow(ConnectionState.Connected)
    override val connectionInfo = MutableStateFlow(SessionConnectionInfo(1))
    override val incoming = MutableSharedFlow<P2pMessage>()
    @Deprecated("Observe pendingFileOffers")
    override val incomingFiles = MutableSharedFlow<P2pFileOffer>()
    val sentKinds = mutableListOf<WireKind>()
    var writeGate: CompletableDeferred<Unit>? = null
    var writeFailure: Exception? = null
    var beforeGenerationCheck: () -> Unit = {}

    override suspend fun sendAtGeneration(message: P2pMessage, generation: Long) {
        beforeGenerationCheck()
        if (generation != connectionInfo.value.generation) throw P2pError.ConnectionFailed("Stale generation")
        send(message)
    }

    override suspend fun send(message: P2pMessage) {
        val budget = PayloadBudget(2L * 1_048_576)
        val decoded = RpcWire.decode((message as P2pMessage.Binary).bytes, budget)
        try { sentKinds += decoded.kind } finally { decoded.release() }
        assertEquals(0L, budget.retainedBytes.value)
        writeFailure?.let { throw it }
        writeGate?.await()
    }

    @Deprecated("RPC must not invoke file-transfer paths")
    override suspend fun sendFile(
        name: String, sizeBytes: Long, mimeType: String?, source: RawSource,
    ): P2pFileTransfer = error("File-transfer bypass")

    override suspend fun close() { state.value = ConnectionState.Closed }
}

@OptIn(ExperimentalCoroutinesApi::class)
class SessionRpcLinkTest {
    @Test
    fun responsesAndControlTakePriorityWithoutPreemptingAnActiveNotification() = runTest {
        val session = LinkTestSession()
        val budget = PayloadBudget(8L * 1_048_576)
        val notifications = PayloadBudget(1_048_576)
        val link = SessionRpcLink(session, backgroundScope, budget, notifications, RpcClock { 0 })
        link.start({}, {})
        val gate = CompletableDeferred<Unit>()
        session.writeGate = gate
        val message = WireMessage(
            WireKind.Notify, TEST_REQUEST, TEST_INCARNATION, "changed", 1, body = testBody("\"n\"", budget),
        )
        assertNotNull(link.offer(message, 10_000, notification = true))
        runCurrent() // First write is active, and must still consume an entry/byte lease.
        repeat(15) { assertNotNull(link.offer(message, 10_000, notification = true)) }
        assertNull(link.offer(message, 10_000, notification = true))
        assertNotNull(link.offer(WireMessage(WireKind.Hello, TEST_SECOND), 10_000))
        gate.complete(Unit)
        runCurrent()
        assertEquals(listOf(WireKind.Notify, WireKind.Hello) + List(15) { WireKind.Notify }, session.sentKinds)
        link.close()
        runCurrent()
        message.release()
        assertEquals(0L, notifications.retainedBytes.value)
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun globalNotificationBudgetSpansPeersAndReleasesOnTeardown() = runTest {
        val budget = PayloadBudget(8L * 1_048_576)
        val notifications = PayloadBudget(1_048_576)
        val links = List(9) {
            SessionRpcLink(LinkTestSession(), backgroundScope, budget, notifications, RpcClock { 0 })
        }
        val message = WireMessage(
            WireKind.Notify, TEST_REQUEST, TEST_INCARNATION, "changed", 1,
            body = testBody("\"" + "n".repeat(15_998) + "\"", budget),
        )
        repeat(8) { peer ->
            repeat(8) { assertNotNull(links[peer].offer(message, 10_000, notification = true)) }
        }
        assertNotNull(links.last().offer(message, 10_000, notification = true))
        assertNull(links.last().offer(message, 10_000, notification = true))
        assertTrue(notifications.retainedBytes.value <= notifications.capacityBytes)
        links.forEach { it.close() }
        message.release()
        assertEquals(0L, notifications.retainedBytes.value)
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun aQueuedMessageCannotCrossConnectionGenerationsOrSurviveCancellation() = runTest {
        val session = LinkTestSession()
        val budget = PayloadBudget(4096)
        val link = SessionRpcLink(session, backgroundScope, budget, PayloadBudget(1024), RpcClock { 0 })
        val first = assertNotNull(link.offer(WireMessage(WireKind.Hello, TEST_REQUEST), 10_000))
        val cancelled = assertNotNull(link.offer(WireMessage(WireKind.Hello, TEST_SECOND), 10_000))
        assertTrue(cancelled.cancelQueued())
        session.connectionInfo.value = SessionConnectionInfo(2)
        link.start({}, {})
        runCurrent()
        assertFalse(first.started)
        assertFalse(first.completion.await())
        assertFalse(cancelled.completion.await())
        assertTrue(session.sentKinds.isEmpty())
        link.close()
        runCurrent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun generationChangeAfterDequeueStillCannotWriteOnTheReplacementConnection() = runTest {
        val session = LinkTestSession()
        val budget = PayloadBudget(4096)
        val link = SessionRpcLink(session, backgroundScope, budget, PayloadBudget(1024), RpcClock { 0 })
        var reachedAtomicBoundary = false
        session.beforeGenerationCheck = {
            reachedAtomicBoundary = true
            session.connectionInfo.value = SessionConnectionInfo(2)
        }
        val ticket = assertNotNull(link.offer(WireMessage(WireKind.Hello, TEST_REQUEST), 10_000))
        link.start({}, {})
        runCurrent()
        assertTrue(reachedAtomicBoundary)
        assertTrue(ticket.started) // Conservative ambiguity; no bytes reached the replacement in this fixture.
        assertFalse(ticket.completion.await())
        assertTrue(session.sentKinds.isEmpty())
        link.close()
        runCurrent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun callbackCancellationClosesTheLinkInsteadOfLeavingADeafConnection() = runTest {
        val session = LinkTestSession()
        val budget = PayloadBudget(4096)
        val link = SessionRpcLink(session, backgroundScope, budget, PayloadBudget(1024), RpcClock { 0 })
        var detached = 0
        link.start(
            onMessage = { throw CancellationException("Application authorization cancelled") },
            onClosed = { detached++ },
        )
        session.incoming.emit(P2pMessage.Binary(RpcWire.encode(WireMessage(WireKind.Hello, TEST_REQUEST))))
        runCurrent()
        assertEquals(ConnectionState.Closed, session.state.value)
        assertEquals(0, session.incoming.subscriptionCount.value)
        assertEquals(1, detached)
        assertNull(link.offer(WireMessage(WireKind.Hello, TEST_SECOND), 10_000))
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun writerCancellationFinishesTheActiveTicketAndDrainsUnsentWork() = runTest {
        val session = LinkTestSession()
        val budget = PayloadBudget(4096)
        val link = SessionRpcLink(session, backgroundScope, budget, PayloadBudget(1024), RpcClock { 0 })
        session.writeFailure = CancellationException("Send cancelled at the core boundary")
        var detached = 0
        link.start({}, { detached++ })
        val first = assertNotNull(link.offer(WireMessage(WireKind.Hello, TEST_REQUEST), 10_000))
        val second = assertNotNull(link.offer(WireMessage(WireKind.Hello, TEST_SECOND), 10_000))
        runCurrent()
        assertTrue(first.started)
        assertFalse(first.completion.await())
        assertFalse(second.started)
        assertFalse(second.completion.await())
        assertEquals(listOf(WireKind.Hello), session.sentKinds)
        assertEquals(ConnectionState.Closed, session.state.value)
        assertEquals(1, detached)
        assertEquals(0L, budget.retainedBytes.value)
    }
}
