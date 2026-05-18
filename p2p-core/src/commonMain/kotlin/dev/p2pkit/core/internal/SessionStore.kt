package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.PeerId
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Single source of truth for [SessionManager]'s session bookkeeping.
 *
 * Consolidates three pieces of state that previously lived as separate
 * fields on SessionManager:
 *   - [byPeer] — the active session per peer id (used for connect
 *     idempotency and simultaneous-open arbitration)
 *   - [pending] — in-flight connect attempts per peer id (used to coalesce
 *     concurrent `connect(peer)` calls onto one transport.connect)
 *   - the published [sessions] StateFlow (mirrored to `P2pKit.sessions`)
 *
 * Every mutation method takes [mutex] and mutates all three fields inside
 * the same locked block. The mutex guards in-memory state and StateFlow
 * publication only — no network I/O, no coroutine startup, and no
 * session-lifecycle calls happen under the lock. Callers act on the
 * returned [ConnectDecision] / [RegisterOutcome] outside the lock.
 *
 * This replaces the previous "active map + _sessions StateFlow updated in
 * tandem by convention" model: every fix in that area (commits b6ffb31,
 * cc4e557) was a missed dual-update. The "always update both" rule is now
 * structural — there is one class, one lock, one set of methods, and no
 * way to mutate one field without mutating the other.
 */
internal class SessionStore(private val logger: P2pLogger) {

    private val mutex = Mutex()
    private val byPeer: MutableMap<PeerId, P2pSession> = mutableMapOf()
    private val pending: MutableMap<PeerId, CompletableDeferred<P2pSession>> = mutableMapOf()

    private val _sessions = MutableStateFlow<List<P2pSession>>(emptyList())
    val sessions: StateFlow<List<P2pSession>> = _sessions.asStateFlow()

    /**
     * Atomic decision under the mutex for an outgoing `connect(peer)` call.
     * Returns one of three outcomes; the caller acts on it outside the lock:
     *
     *  - [ConnectDecision.Existing] — an active, non-terminal session for
     *    this peer already exists. Return it as-is.
     *  - [ConnectDecision.JoinPending] — another caller has an in-flight
     *    connect for this peer. Await their deferred.
     *  - [ConnectDecision.BecomeConnector] — no active session and no
     *    in-flight connect; this caller becomes the connector. The store
     *    has registered the returned deferred under [pending]; the caller
     *    MUST eventually call [endPending] (success or failure).
     *
     * If an existing entry is in a terminal state, it is evicted from both
     * [byPeer] and [sessions] atomically before the in-flight check.
     * Preserves the "terminal existing — remove from BOTH" behaviour
     * introduced in commit b6ffb31.
     */
    suspend fun startOrJoin(peerId: PeerId): ConnectDecision = mutex.withLock {
        val existing = byPeer[peerId]
        if (existing != null && existing.state.value in ACTIVE_STATES) {
            return@withLock ConnectDecision.Existing(existing)
        }
        if (existing != null) {
            byPeer.remove(peerId)
            _sessions.value = _sessions.value.filter { it !== existing }
        }
        val inFlight = pending[peerId]
        if (inFlight != null) {
            ConnectDecision.JoinPending(inFlight)
        } else {
            val fresh = CompletableDeferred<P2pSession>()
            pending[peerId] = fresh
            ConnectDecision.BecomeConnector(fresh)
        }
    }

    /**
     * Remove the in-flight pending entry for [peerId]. Identity-checked so
     * a late call cannot remove a fresh deferred that has since taken the
     * slot. Idempotent — repeated calls are a no-op.
     */
    suspend fun endPending(
        peerId: PeerId,
        expected: CompletableDeferred<P2pSession>
    ): Unit = mutex.withLock {
        if (pending[peerId] === expected) pending.remove(peerId)
    }

    /**
     * Register a freshly-handshaked session, arbitrating simultaneous opens.
     *
     * If two peers `connect()` each other at the same instant each side ends
     * up with two `P2pSession` candidates — one outgoing, one incoming. To
     * keep the public contract of "one session per peer in `kit.sessions`"
     * honest, both sides apply the same deterministic tie-break:
     *
     *  - **The smaller-id peer keeps its OUTGOING session** (closes its incoming).
     *  - **The larger-id peer keeps its INCOMING session** (closes its outgoing).
     *
     * Both sides keep the same physical TCP connection (the one initiated by
     * the smaller-id peer). The other connection is closed on both ends.
     *
     * Returns the [RegisterOutcome] so the caller can route the winner back
     * to the connecting deferred (outgoing) or to `P2pKit.incomingSessions`
     * (incoming), and close the loser outside the lock. Closing the loser
     * is the caller's responsibility — this method does NOT touch session
     * lifecycles.
     */
    suspend fun tryRegister(
        peerId: PeerId,
        session: P2pSession,
        isIncoming: Boolean,
        localPeerIdValue: String
    ): RegisterOutcome = mutex.withLock {
        val existing = byPeer[peerId]
        val existingState = existing?.state?.value
        if (existing != null && existingState in ACTIVE_STATES) {
            val newWinsLocally = if (localPeerIdValue < peerId.value) {
                // We're the smaller-id side — keep our outgoing, reject our incoming.
                !isIncoming
            } else {
                // We're the larger-id side (or equal, which is impossible
                // by construction) — keep our incoming, reject our outgoing.
                isIncoming
            }
            if (newWinsLocally) {
                byPeer[peerId] = session
                _sessions.value = _sessions.value.filter { it !== existing } + session
                RegisterOutcome.Replaced(winner = session, loser = existing)
            } else {
                RegisterOutcome.Rejected(winner = existing, loser = session)
            }
        } else {
            // Existing may be `null` OR in a terminal state (Closed / Failed /
            // Closing / Idle). In the terminal case the per-session terminal
            // watcher is either pending or mid-run and the existing session
            // may still be in [_sessions]. Filter it out atomically with the
            // add so the public list never has both the dead and the fresh
            // session for the same peer for any observable window — the iOS
            // sample's PeerRow ↔ session matching iterates by peerId and
            // would otherwise see two rows for the same peer.
            byPeer[peerId] = session
            _sessions.value = if (existing != null) {
                _sessions.value.filter { it !== existing } + session
            } else {
                _sessions.value + session
            }
            RegisterOutcome.Accepted(session = session)
        }
    }

    /**
     * Remove [session] from both stores. The [byPeer] entry is removed only
     * if it is still this exact session instance (`===`); [sessions] is
     * filtered unconditionally. Called by SessionManager's per-session
     * terminal watcher when the session reaches [ConnectionState.Closed]
     * or [ConnectionState.Failed].
     */
    suspend fun removeIfMatches(peerId: PeerId, session: P2pSession): Unit = mutex.withLock {
        if (byPeer[peerId] === session) byPeer.remove(peerId)
        _sessions.value = _sessions.value.filter { it !== session }
    }

    /**
     * Snapshot of currently-active session instances. Used by
     * `closeAllSessions` and the `Unsatisfied` path in
     * `SessionManager.applyPathChange` to iterate sessions outside the lock.
     */
    suspend fun activeSnapshot(): List<P2pSession> = mutex.withLock {
        byPeer.values.toList()
    }

    /**
     * Lock-free best-effort lookup of a session's registration. Read by
     * [P2pSessionImpl.routeEvents] before each `Message` emit to detect
     * zombie emissions — sessions still pumping messages into the public
     * incoming flow after they've been evicted/replaced in the store.
     *
     * Diagnostics-only — does NOT take [mutex]. A microsecond-stale read
     * is fine; what matters is steady-state divergence (the session
     * keeps emitting but is gone from both maps for many emissions in a
     * row), which the zombie watchdog logs as a ZOMBIE warning.
     */
    fun registrationOf(session: P2pSession): SessionRegistration {
        val current = byPeer[session.peer.id]
        return SessionRegistration(
            activeSessionId = current?.id,
            isInPublicList = _sessions.value.any { it === session }
        )
    }

    companion object {
        val ACTIVE_STATES: Set<ConnectionState> = setOf(
            ConnectionState.Connecting,
            ConnectionState.Handshaking,
            ConnectionState.Connected,
            ConnectionState.Reconnecting
        )
    }
}

/** Outcome of [SessionStore.startOrJoin]; drives the outgoing `connect()` flow. */
internal sealed class ConnectDecision {
    data class Existing(val session: P2pSession) : ConnectDecision()
    data class JoinPending(val deferred: CompletableDeferred<P2pSession>) : ConnectDecision()
    data class BecomeConnector(val deferred: CompletableDeferred<P2pSession>) : ConnectDecision()
}

/** Outcome of [SessionStore.tryRegister]; drives the post-registration routing. */
internal sealed class RegisterOutcome {
    data class Accepted(val session: P2pSession) : RegisterOutcome()
    data class Replaced(val winner: P2pSession, val loser: P2pSession) : RegisterOutcome()
    data class Rejected(val winner: P2pSession, val loser: P2pSession) : RegisterOutcome()
}
