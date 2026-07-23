package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.test.runTest
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * AUDIT-2026-07 (SEC-1, decision #9a) / coverage plan P1-26 companion
 * (SEC-1(b)): [SessionStore.tryRegister]'s total-active-session admission
 * bound ([MAX_TOTAL_ACTIVE_SESSIONS]), exercised at the store level where
 * every branch is deterministic:
 *
 *  1. Boundary: exactly [MAX_TOTAL_ACTIVE_SESSIONS] net-new incoming
 *     registrations are accepted; the next one is refused
 *     ([RegisterOutcome.RefusedAtCapacity]) and leaves the store untouched.
 *  2. Outgoing registrations are never refused by the bound (app-initiated
 *     connects are exempt by design).
 *  3. Simultaneous-open arbitration still runs at capacity — an incoming
 *     candidate for a peer with an existing active session is Replaced /
 *     Rejected per the id tie-break, never RefusedAtCapacity (no net
 *     session growth).
 *  4. Only ACTIVE sessions count: terminal-but-not-yet-evicted entries do
 *     not block admission of a live peer.
 *
 * Runs with `strictInvariants = true` so a refusal that corrupted the
 * store's bookkeeping would fail loudly.
 */
@Suppress("OVERRIDE_DEPRECATION")
class SessionStoreCapacityTest {

    private fun newStore() = SessionStore(P2pLogger.NoOp, strictInvariants = true)

    /** Larger than every "peer-NNN" id, so incoming candidates win arbitration. */
    private val largerLocalId = "zzzz-local"

    /** Smaller than every "peer-NNN" id, so incoming candidates lose arbitration. */
    private val smallerLocalId = "aaaa-local"

    private suspend fun fillToCapacity(store: SessionStore): List<CapStubSession> {
        val registered = (1..MAX_TOTAL_ACTIVE_SESSIONS).map { i ->
            val session = stubSession("peer-$i")
            val outcome = store.tryRegister(
                peerId = session.peer.id,
                session = session,
                // Mixed provenance below the cap: half incoming, half outgoing.
                isIncoming = i % 2 == 0,
                localPeerIdValue = largerLocalId
            )
            assertIs<RegisterOutcome.Accepted>(
                outcome,
                "registration $i of $MAX_TOTAL_ACTIVE_SESSIONS must be accepted (below/at the bound)"
            )
            session
        }
        assertEquals(MAX_TOTAL_ACTIVE_SESSIONS, store.sessions.value.size)
        return registered
    }

    @Test
    fun netNewIncomingBeyondTheBoundIsRefusedAndStoreIsUntouched() = runTest {
        val store = newStore()
        fillToCapacity(store)

        val excess = stubSession("peer-excess")
        val outcome = store.tryRegister(
            peerId = excess.peer.id,
            session = excess,
            isIncoming = true,
            localPeerIdValue = largerLocalId
        )

        val refusal = assertIs<RegisterOutcome.RefusedAtCapacity>(outcome)
        assertEquals(excess, refusal.session)
        // The refused session was never added to either store view.
        assertEquals(MAX_TOTAL_ACTIVE_SESSIONS, store.sessions.value.size)
        assertTrue(
            store.sessions.value.none { it === excess },
            "a refused session must not appear in the published sessions list"
        )
        assertTrue(
            store.activeSnapshot().none { it === excess },
            "a refused session must not appear in the byPeer snapshot"
        )
    }

    @Test
    fun outgoingRegistrationIsNeverRefusedByTheBound() = runTest {
        val store = newStore()
        fillToCapacity(store)

        // App-initiated outgoing connect while at the bound: accepted.
        val outgoing = stubSession("peer-outgoing-at-cap")
        val outcome = store.tryRegister(
            peerId = outgoing.peer.id,
            session = outgoing,
            isIncoming = false,
            localPeerIdValue = largerLocalId
        )
        assertIs<RegisterOutcome.Accepted>(outcome)
        assertEquals(MAX_TOTAL_ACTIVE_SESSIONS + 1, store.sessions.value.size)

        // ...and a subsequent net-new incoming is still refused (the count is
        // now past the bound; outgoing growth does not open inbound slots).
        val incoming = stubSession("peer-incoming-after")
        assertIs<RegisterOutcome.RefusedAtCapacity>(
            store.tryRegister(
                peerId = incoming.peer.id,
                session = incoming,
                isIncoming = true,
                localPeerIdValue = largerLocalId
            )
        )
    }

    @Test
    fun simultaneousOpenArbitrationStillRunsAtCapacity() = runTest {
        val store = newStore()
        val registered = fillToCapacity(store)
        val existing = registered.first() // "peer-1", active

        // Incoming candidate for a peer that already has an active session:
        // arbitration, never a capacity refusal (replace = no net growth).
        // Larger local id keeps its incoming -> Replaced.
        val replacing = stubSession("peer-1", id = "candidate-replacing")
        val replaced = assertIs<RegisterOutcome.Replaced>(
            store.tryRegister(
                peerId = existing.peer.id,
                session = replacing,
                isIncoming = true,
                localPeerIdValue = largerLocalId
            )
        )
        assertEquals(replacing, replaced.winner)
        assertEquals(existing, replaced.loser)
        assertEquals(
            MAX_TOTAL_ACTIVE_SESSIONS, store.sessions.value.size,
            "Replaced arbitration must cause no net session growth"
        )

        // Smaller local id keeps its outgoing -> the incoming candidate is
        // Rejected (still arbitration, not a capacity refusal).
        val losing = stubSession("peer-2", id = "candidate-losing")
        val rejected = assertIs<RegisterOutcome.Rejected>(
            store.tryRegister(
                peerId = losing.peer.id,
                session = losing,
                isIncoming = true,
                localPeerIdValue = smallerLocalId
            )
        )
        assertEquals(losing, rejected.loser)
        assertEquals(MAX_TOTAL_ACTIVE_SESSIONS, store.sessions.value.size)
    }

    @Test
    fun terminalSessionsDoNotCountTowardTheBound() = runTest {
        val store = newStore()
        val registered = fillToCapacity(store)

        // One session reaches a terminal state but has NOT yet been evicted
        // by the terminal watcher — it must stop counting immediately.
        registered.first().moveTo(ConnectionState.Closed)

        val fresh = stubSession("peer-fresh")
        assertIs<RegisterOutcome.Accepted>(
            store.tryRegister(
                peerId = fresh.peer.id,
                session = fresh,
                isIncoming = true,
                localPeerIdValue = largerLocalId
            ),
            "a terminal (not yet evicted) session must not block admission of a live peer"
        )
    }

    private fun stubSession(peerIdValue: String, id: String = "session-$peerIdValue") =
        CapStubSession(
            peer = Peer(
                id = PeerId(peerIdValue),
                name = peerIdValue,
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            ),
            id = id
        )
}

/**
 * Minimal [P2pSession] stand-in: the store only reads [peer], [state], and
 * instance identity. Send/file members fail loudly if ever touched.
 */
private class CapStubSession(
    override val peer: Peer,
    override val id: String,
    initialState: ConnectionState = ConnectionState.Connected
) : P2pSession {
    private val _state = MutableStateFlow(initialState)
    override val state: StateFlow<ConnectionState> = _state
    override val incoming: SharedFlow<P2pMessage> = MutableSharedFlow()
    @Deprecated("Observe pendingFileOffers")
    override val incomingFiles: SharedFlow<P2pFileOffer> = MutableSharedFlow()

    fun moveTo(state: ConnectionState) {
        _state.value = state
    }

    override suspend fun send(message: P2pMessage): Unit =
        error("CapStubSession.send is not supported")

    @Deprecated("Legacy fixture overload")
    override suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource
    ): P2pFileTransfer = error("CapStubSession.sendFile is not supported")

    override suspend fun close() {
        _state.value = ConnectionState.Closed
    }
}
