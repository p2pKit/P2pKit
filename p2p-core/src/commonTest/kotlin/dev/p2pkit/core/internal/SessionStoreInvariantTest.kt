package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.RecordingLogger
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runTest
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

/**
 * Enforcement tests for [SessionStore]'s `strictInvariants` mode (#19).
 *
 * Production runs with `strictInvariants = false`: a `checkInvariants`
 * violation is a loud `logger.warn`, never a crash. But the suites run with
 * a NoOp/quiet logger, so warn-only enforcement would let a future store
 * regression pass every test silently. These tests pin the strict-mode
 * contract:
 *
 *  1. a genuinely inconsistent state (forced via the test-only
 *     [SessionStore.forceInvariantViolationForTest] seam — the public
 *     mutators maintain the invariants and cannot produce one) THROWS
 *     under `strictInvariants = true`;
 *  2. the same inconsistency only warns under the production default;
 *  3. a valid mutation sequence never false-positives under strict mode.
 */
class SessionStoreInvariantTest {

    @Test
    fun registrationLookupIsSafeDuringConcurrentMutation() = runTest {
        val store = SessionStore(P2pLogger.NoOp, strictInvariants = true)
        val peer = syntheticPeer("peer-concurrent", "Concurrent")
        val probe = StubSession(peer = peer, id = "probe")
        val finished = CompletableDeferred<Unit>()

        coroutineScope {
            val readers = List(4) {
                launch(Dispatchers.Default) {
                    while (!finished.isCompleted) {
                        store.registrationOf(probe)
                    }
                }
            }
            repeat(2_000) { index ->
                val candidate = StubSession(peer = peer, id = "session-$index")
                assertIs<RegisterOutcome.Accepted>(
                    store.tryRegister(
                        peerId = peer.id,
                        session = candidate,
                        isIncoming = false,
                        localPeerIdValue = "local"
                    )
                )
                assertEquals(candidate.id, store.registrationOf(candidate).activeSessionId)
                store.removeIfMatches(peer.id, candidate)
            }
            finished.complete(Unit)
            readers.forEach { it.join() }
        }

        assertEquals(null, store.registrationOf(probe).activeSessionId)
        assertTrue(store.sessions.value.isEmpty())
    }

    @Test
    fun strictModeThrowsOnForcedInconsistency() = runTest {
        val store = SessionStore(P2pLogger.NoOp, strictInvariants = true)
        val failure = assertFailsWith<IllegalStateException> {
            store.forceInvariantViolationForTest(StubSession(peer = syntheticPeer("peer-a", "A")))
        }
        val message = failure.message ?: ""
        assertTrue(
            message.contains("INVARIANT"),
            "strict-mode failure should identify itself as an invariant violation, was: $message"
        )
        assertTrue(
            message.contains("byPeer entry missing from published sessions list"),
            "strict-mode failure should name the violated invariant (I-store-membership), was: $message"
        )
    }

    @Test
    fun defaultModeWarnsWithoutThrowingOnSameInconsistency() = runTest {
        val logger = RecordingLogger()
        val store = SessionStore(logger) // strictInvariants defaults to false = production behavior
        // Must NOT throw — production is log-don't-crash.
        store.forceInvariantViolationForTest(StubSession(peer = syntheticPeer("peer-a", "A")))
        // ...but the violation must still have been detected and warned,
        // proving the forced state is a real inconsistency, not a no-op.
        assertEquals(1, logger.warnings.size, "expected exactly one invariant warning")
        assertTrue(
            logger.warnings.single().contains("INVARIANT"),
            "warning should identify the invariant violation, was: ${logger.warnings.single()}"
        )
    }

    @Test
    fun strictModeDoesNotThrowOnValidOperationSequence() = runTest {
        val store = SessionStore(P2pLogger.NoOp, strictInvariants = true)
        val peerId = PeerId("peer-b")
        val localPeerIdValue = "aaaa-local" // < "peer-b": smaller-id side keeps its outgoing
        val outgoing = StubSession(peer = syntheticPeer("peer-b", "B"), id = "session-outgoing")

        // connect(): become the connector, register the handshaked session,
        // release the pending slot — every step runs checkInvariants.
        val decision = store.startOrJoin(peerId)
        val connector = assertIs<ConnectDecision.BecomeConnector>(decision)
        val registered = store.tryRegister(
            peerId = peerId,
            session = outgoing,
            isIncoming = false,
            localPeerIdValue = localPeerIdValue
        )
        assertIs<RegisterOutcome.Accepted>(registered)
        store.endPending(peerId, connector.deferred)

        // Second connect() to the same active peer joins the existing session.
        val second = store.startOrJoin(peerId)
        assertSame(outgoing, assertIs<ConnectDecision.Existing>(second).session)

        // Simultaneous open: the incoming candidate loses the tie-break
        // (we are the smaller-id side), leaving the store untouched.
        val incomingCandidate = StubSession(peer = syntheticPeer("peer-b", "B"), id = "session-incoming")
        val arbitration = store.tryRegister(
            peerId = peerId,
            session = incomingCandidate,
            isIncoming = true,
            localPeerIdValue = localPeerIdValue
        )
        assertIs<RegisterOutcome.Rejected>(arbitration)

        // Terminal eviction: the active session dies, a fresh one replaces
        // it atomically (the filter-then-add path in tryRegister).
        outgoing.moveTo(ConnectionState.Closed)
        val fresh = StubSession(peer = syntheticPeer("peer-b", "B"), id = "session-fresh")
        val replaced = store.tryRegister(
            peerId = peerId,
            session = fresh,
            isIncoming = true,
            localPeerIdValue = localPeerIdValue
        )
        assertIs<RegisterOutcome.Accepted>(replaced)
        assertEquals(listOf<P2pSession>(fresh), store.sessions.value)

        // Terminal-watcher cleanup path.
        fresh.moveTo(ConnectionState.Closed)
        store.removeIfMatches(peerId, fresh)
        assertTrue(store.sessions.value.isEmpty())
        // Reaching here without an IllegalStateException is the point:
        // strict mode never fires on invariant-preserving operations.
    }

    private fun syntheticPeer(id: String, name: String): Peer = Peer(
        id = PeerId(id),
        name = name,
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )
}

/**
 * Minimal [P2pSession] stand-in for exercising [SessionStore] bookkeeping:
 * the store only reads [peer], [state], and instance identity. Send/file
 * members are never touched by the store and fail loudly if called.
 */
private class StubSession(
    override val peer: Peer,
    override val id: String = "session-${peer.id.value}",
    initialState: ConnectionState = ConnectionState.Connected
) : P2pSession {
    private val _state = MutableStateFlow(initialState)
    override val state: StateFlow<ConnectionState> = _state
    override val incoming: SharedFlow<P2pMessage> = MutableSharedFlow()
    override val incomingFiles: SharedFlow<P2pFileOffer> = MutableSharedFlow()

    fun moveTo(state: ConnectionState) {
        _state.value = state
    }

    override suspend fun send(message: P2pMessage): Unit =
        error("StubSession.send is not supported")

    override suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource
    ): P2pFileTransfer = error("StubSession.sendFile is not supported")

    override suspend fun close() {
        _state.value = ConnectionState.Closed
    }
}
