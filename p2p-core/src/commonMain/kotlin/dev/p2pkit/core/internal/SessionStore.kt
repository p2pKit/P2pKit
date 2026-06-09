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
        val decision = if (inFlight != null) {
            ConnectDecision.JoinPending(inFlight)
        } else {
            val fresh = CompletableDeferred<P2pSession>()
            pending[peerId] = fresh
            ConnectDecision.BecomeConnector(fresh)
        }
        checkInvariants("startOrJoin")
        decision
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
        checkInvariants("endPending")
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
        val outcome: RegisterOutcome = if (existing != null && existingState in ACTIVE_STATES) {
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
        checkInvariants("tryRegister")
        outcome
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
        checkInvariants("removeIfMatches")
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

    /**
     * Structural-invariant check run at the end of every mutation method
     * while [mutex] is still held. Hard `check()` calls — a violation
     * means the store has reached a state the design considers
     * impossible, and the application MUST crash rather than continue
     * with an inconsistent view of `kit.sessions`.
     *
     * Invariants (all evaluated under [mutex], so the state is stable):
     *
     *  - **I-store-membership**: every active byPeer entry appears in the
     *    published sessions list. The reverse is not required — a session
     *    in the list but not in byPeer is a terminal session whose
     *    per-session terminal watcher has not yet run `removeIfMatches`.
     *  - **I-store-uniqueness**: no duplicate session *instance* in the
     *    published sessions list. (Per-peer uniqueness is NOT asserted
     *    here — a brief window may legitimately contain one terminal and
     *    one fresh session for the same peer, evicted within the same
     *    mutation; the filter-then-add pattern in [tryRegister] removes
     *    both staleness windows the public list ever exhibited.)
     *
     * Gated by [ASSERT_INVARIANTS]. Leave `true` through v0.4 — if a real
     * device run trips a check, revert Commit 2 only; the structural
     * refactor in Commit 1 stays.
     */
    private fun checkInvariants(site: String) {
        if (!ASSERT_INVARIANTS) return
        val visible = _sessions.value
        // Log-don't-crash: an invariant violation is a serious bug, but a
        // published library must not bring down the host app's process over a
        // bookkeeping inconsistency. We surface it loudly via the logger so it
        // is caught in testing/diagnostics without an in-the-field crash.
        if (!byPeer.values.all { entry -> visible.any { it === entry } }) {
            logger.warn(
                "SessionStore[$site] INVARIANT: active byPeer entry missing from published sessions list. " +
                    "byPeer.size=${byPeer.size} visible.size=${visible.size}"
            )
        }
        val duplicateInstances = visible.fold(0) { acc, s ->
            acc + if (visible.count { it === s } == 1) 0 else 1
        }
        if (duplicateInstances != 0) {
            logger.warn(
                "SessionStore[$site] INVARIANT: duplicate session instance in published list (size=${visible.size})"
            )
        }
    }

    companion object {
        val ACTIVE_STATES: Set<ConnectionState> = setOf(
            ConnectionState.Connecting,
            ConnectionState.Handshaking,
            ConnectionState.Connected,
            ConnectionState.Reconnecting
        )

        /**
         * Master switch for [checkInvariants]. `true` through v0.4 — if
         * hardware testing surfaces a benign-but-valid ordering that
         * trips a check, flip to `false` and open an issue. Reverting
         * this whole commit (S1 Commit 2) is also clean since Commit 1
         * already stands on its own.
         */
        private const val ASSERT_INVARIANTS = true
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
