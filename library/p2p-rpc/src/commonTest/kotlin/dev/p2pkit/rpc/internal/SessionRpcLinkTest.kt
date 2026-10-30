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
import dev.p2pkit.rpc.RpcApplicationSession
import dev.p2pkit.rpc.RpcLimits
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.test.assertSame
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds

private class LinkTestSession(index: Int = 0) : P2pSession {
    override val id = "rpc-test-session-$index"
    override val peer = Peer(PeerId("rpc-peer-$index"), "fixture", Platform.UNKNOWN, setOf(TransportKind.LAN))
    override val peerIdentity = PeerIdentity(peer.id, testFingerprint(index))
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
    fun scopedWriterRechecksRevocationExpiryAndGenerationAfterSuspendedPolicy() = runTest {
        for (change in listOf("revoke", "session-expiry", "ticket-expiry", "generation", "disconnect", "trust")) {
            val session = LinkTestSession()
            val budget = PayloadBudget(8192)
            val notificationBudget = PayloadBudget(4096)
            val clock = RpcClock { testScheduler.currentTime }
            val applicationSession = RpcApplicationSession(testFingerprint(), "employee", "login",
                if (change == "session-expiry") 1.milliseconds else Duration.INFINITE, clock)
            val entered = CompletableDeferred<Unit>()
            val release = CompletableDeferred<Unit>()
            var trusted = true
            val guard = RpcSendAuthorization(applicationSession, stillAllowed = { trusted }) {
                entered.complete(Unit); release.await(); true
            }
            val link = SessionRpcLink(session, backgroundScope, budget, notificationBudget, clock)
            val message = WireMessage(WireKind.Notify, TEST_REQUEST, TEST_INCARNATION, "changed", 1,
                body = testBody("\"private\"", budget))
            val ticket = assertNotNull(link.offer(message,
                if (change == "ticket-expiry") clock.now() + 1 else clock.now() + 10_000,
                notification = true, authorization = guard))
            try {
                link.start({}, {}); runCurrent(); assertTrue(entered.isCompleted)
                when (change) {
                    "revoke" -> applicationSession.revoke()
                    "session-expiry", "ticket-expiry" -> advanceTimeBy(1)
                    "generation" -> session.connectionInfo.value = SessionConnectionInfo(2)
                    "disconnect" -> session.state.value = ConnectionState.Reconnecting
                    "trust" -> trusted = false
                }
                release.complete(Unit); runCurrent()
                assertFalse(ticket.started, "No commitment after $change")
                assertFalse(ticket.completion.await())
                assertTrue(session.sentKinds.isEmpty())
                assertEquals(0L, notificationBudget.retainedBytes.value)
            } finally { release.complete(Unit); link.close(); runCurrent(); message.release() }
            assertEquals(0L, budget.retainedBytes.value)
        }
    }

    @Test
    fun closeReleasesDequeuedScopedTicketWhileItsAuthorizerIsSuspended() = runTest {
        val session = LinkTestSession()
        val budget = PayloadBudget(8192)
        val notificationBudget = PayloadBudget(4096)
        val entered = CompletableDeferred<Unit>()
        val applicationSession = RpcApplicationSession(testFingerprint(), "employee", "login")
        val link = SessionRpcLink(session, backgroundScope, budget, notificationBudget, RpcClock { 0 })
        val message = WireMessage(WireKind.Notify, TEST_REQUEST, TEST_INCARNATION, "changed", 1,
            body = testBody("\"private\"", budget))
        val ticket = assertNotNull(link.offer(message, 10_000, notification = true,
            authorization = RpcSendAuthorization(applicationSession) {
                entered.complete(Unit); kotlinx.coroutines.awaitCancellation()
            }))
        link.start({}, {}); runCurrent(); assertTrue(entered.isCompleted)
        link.close(); runCurrent(); message.release()
        assertFalse(ticket.started)
        assertFalse(ticket.completion.await())
        assertTrue(session.sentKinds.isEmpty())
        assertEquals(0L, notificationBudget.retainedBytes.value)
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun authorizerErrorReleasesUnstartedTicketAndPropagatesOriginalError() = runTest {
        val marker = object : Error("writer authorization fixture") { val owner = Any() }
        val errors = mutableListOf<Throwable>()
        val owner = SupervisorJob()
        val scope = CoroutineScope(coroutineContext + owner + CoroutineExceptionHandler { _, failure ->
            errors += failure
        })
        val session = LinkTestSession()
        val budget = PayloadBudget(8192)
        val notificationBudget = PayloadBudget(4096)
        val applicationSession = RpcApplicationSession(testFingerprint(), "employee", "login")
        val link = SessionRpcLink(session, scope, budget, notificationBudget, RpcClock { 0 })
        val message = WireMessage(WireKind.Notify, TEST_REQUEST, TEST_INCARNATION, "changed", 1,
            body = testBody("\"private\"", budget))
        val ticket = assertNotNull(link.offer(message, 10_000, notification = true,
            authorization = RpcSendAuthorization(applicationSession) { throw marker }))
        try {
            link.start({}, {}); runCurrent()
            assertSame(marker, errors.single())
            assertFalse(ticket.started)
            assertFalse(ticket.completion.await())
            assertTrue(session.sentKinds.isEmpty())
            assertEquals(0L, notificationBudget.retainedBytes.value)
        } finally { link.close(); owner.cancelAndJoin(); message.release() }
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun sessionRevocationNeverWaitsForAlreadyCommittedNetworkWrite() = runTest {
        val session = LinkTestSession()
        val gate = CompletableDeferred<Unit>()
        session.writeGate = gate
        val budget = PayloadBudget(8192)
        val applicationSession = RpcApplicationSession(testFingerprint(), "employee", "login")
        val link = SessionRpcLink(session, backgroundScope, budget, PayloadBudget(4096), RpcClock { 0 })
        val message = WireMessage(WireKind.Notify, TEST_REQUEST, TEST_INCARNATION, "changed", 1,
            body = testBody("\"private\"", budget))
        val guard = RpcSendAuthorization(applicationSession) { true }
        val first = assertNotNull(link.offer(message, 10_000, notification = true, authorization = guard))
        try {
            link.start({}, {}); runCurrent(); assertTrue(first.started)
            applicationSession.revoke()
            val second = assertNotNull(link.offer(message, 10_000, notification = true, authorization = guard))
            gate.complete(Unit); runCurrent()
            assertTrue(first.completion.await())
            assertFalse(second.started)
            assertFalse(second.completion.await())
            assertEquals(listOf(WireKind.Notify), session.sentKinds)
        } finally { gate.complete(Unit); link.close(); runCurrent(); message.release() }
        assertEquals(0L, budget.retainedBytes.value)
    }

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
    fun profileNotificationBudgetsSpanEveryClientAndDoNotBlockPriorityOrSurviveClose() = runTest {
        for (limits in listOf(RpcLimits.host128(), RpcLimits.host256())) {
            val budget = PayloadBudget(limits.payloadBytes)
            val host = RpcHostEngine(backgroundScope, emptyMap(), limits, budget,
                RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION)
            assertEquals(limits.trustedClients * 8192L, host.notificationBudget.capacityBytes)
            val links = List(limits.trustedClients) { index ->
                SessionRpcLink(LinkTestSession(index), backgroundScope, budget, host.notificationBudget, RpcClock { 0 })
            }
            val message = WireMessage(WireKind.Notify, TEST_REQUEST, TEST_INCARNATION, "changed", 1,
                body = testBody("\"" + "n".repeat(3998) + "\"", budget))
            val bytes = checkNotNull(message.body).size + message.name.length + RpcWire.HEADER_BYTES
            val maximum = (host.notificationBudget.capacityBytes / bytes).toInt()
            try {
                assertTrue(maximum >= links.size, "All peers receive an admission opportunity in this fixture")
                repeat(maximum) { index ->
                    assertNotNull(links[index % links.size].offer(message, 10_000, notification = true))
                }
                assertEquals(maximum * bytes.toLong(), host.notificationBudget.retainedBytes.value)
                assertNull(links[maximum % links.size].offer(message, 10_000, notification = true))
                // Host-wide best-effort saturation cannot consume the response/control lane.
                assertNotNull(links[maximum % links.size].offer(WireMessage(WireKind.Hello, TEST_SECOND), 10_000))
            } finally {
                links.forEach { it.close() }
                message.release()
                host.close()
            }
            assertEquals(0L, host.notificationBudget.retainedBytes.value)
            assertEquals(0L, budget.retainedBytes.value)
        }
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
