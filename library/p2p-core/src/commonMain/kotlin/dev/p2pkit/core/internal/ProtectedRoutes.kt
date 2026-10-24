package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.ProtectedRouteStatus
import dev.p2pkit.core.transport.OutboundRoute
import kotlin.concurrent.atomics.AtomicBoolean
import kotlin.concurrent.atomics.AtomicReference
import kotlin.concurrent.atomics.ExperimentalAtomicApi

/**
 * Finite, process-local retention of routes actually used by authorized outgoing sessions. This is
 * independent of untrusted discovery admission, not a promise of fair unknown-peer discovery.
 *
 * Membership and the terminal seal share one immutable, identity-CAS snapshot. Pending leases belong
 * to their setup transaction, not this map. Neither a delayed callback nor a second installation can
 * restore a retired lease. Application admission and exact session registration remain authoritative.
 */
@OptIn(ExperimentalAtomicApi::class)
internal class ProtectedRoutes(
    private val clock: () -> Long,
    private val onProtected: (ProtectedRouteLease) -> Unit = {},
    private val onRetired: (ProtectedRouteLease) -> Unit = {},
    private val maxRoutes: Int = 64
) {
    init {
        require(maxRoutes in 1..64) { "maxRoutes must be between 1 and 64" }
    }

    private val provenance = Any()
    private val state = AtomicReference(Snapshot())

    fun newLease(
        session: P2pSession,
        route: OutboundRoute,
        isAuthorized: () -> Boolean,
        isRegistered: () -> Boolean,
        recoveryGraceMillis: Long = 30_000
    ): ProtectedRouteLease {
        require(recoveryGraceMillis >= 0) { "recoveryGraceMillis must not be negative" }
        return ProtectedRouteLease(
            this, provenance, session, route, isAuthorized, isRegistered, minOf(recoveryGraceMillis, 30_000)
        ).also {
            if (state.load().closed) it.finish(ProtectedRouteStatus.Retired)
        }
    }

    fun install(lease: ProtectedRouteLease): ProtectedRouteStatus {
        if (!owns(lease)) return ProtectedRouteStatus.Retired
        // Consume before any callback/CAS. A removed installed lease can never reuse its old seed.
        val route = lease.takeCandidate() ?: return lease.status
        val generation = runCatching { lease.session.connectionInfo.value.generation }.getOrDefault(0)
        val candidate = Entry(lease, route, generation)
        while (true) {
            lease.finishedStatus()?.let { return it }
            val current = state.load()
            if (current.closed) return lease.finish(ProtectedRouteStatus.Retired)
            val refusal = invalidReason(candidate, installing = true)
            if (refusal != null) return lease.finish(refusal)
            if (state.load() !== current) continue
            // Dead/revoked owners cannot reserve capacity until a delayed store-removal watcher runs.
            if (prune(current)) continue
            if (state.load() !== current) continue
            if (current.entries.containsKey(lease.peerId) || current.entries.size >= maxRoutes) {
                return lease.finish(ProtectedRouteStatus.CapacityUnavailable)
            }
            if (lease.finishedStatus() != null) continue
            val next = current.next(entries = current.entries + (lease.peerId to candidate))
            if (!state.compareAndSet(current, next)) continue
            if (lease.status == ProtectedRouteStatus.Protected) {
                try {
                    onProtected(lease)
                } catch (_: Throwable) {
                    // An optional peer-list projection must not strand scarce capacity or fail the
                    // otherwise successful authenticated connection. Status still exposes retirement.
                    retire(lease)
                }
            }
            return lease.status
        }
    }

    fun retire(lease: ProtectedRouteLease) {
        if (!owns(lease)) return
        lease.finish(ProtectedRouteStatus.Retired)
        while (true) {
            val current = state.load()
            if (current.closed) return
            val owned = current.entries[lease.peerId]?.takeIf { it.lease === lease }
            // Also advance an empty/nonmatching snapshot. This fences an installation that checked
            // eligibility before finish(), but has not reached its compare-and-set yet.
            val next = current.next(entries = if (owned == null) current.entries else current.entries - lease.peerId)
            if (!state.compareAndSet(current, next)) continue
            if (owned != null) notifyRetired(lease)
            return
        }
    }

    fun close() {
        while (true) {
            val current = state.load()
            if (current.closed) return
            if (!state.compareAndSet(current, current.next(closed = true, entries = emptyMap()))) continue
            // Finish every lease before callbacks. A failing/reentrant callback cannot leave another
            // entry protected or prevent the rest of the retirement notifications.
            current.entries.values.forEach { it.lease.finish(ProtectedRouteStatus.Retired) }
            current.entries.values.forEach { notifyRetired(it.lease) }
            return
        }
    }

    internal fun statusOf(lease: ProtectedRouteLease): ProtectedRouteStatus {
        if (!owns(lease)) return ProtectedRouteStatus.Retired
        return if (locateLive(lease) != null) ProtectedRouteStatus.Protected
        else lease.finishedStatus() ?: ProtectedRouteStatus.Unsupported
    }

    internal fun routeForUse(lease: ProtectedRouteLease): OutboundRoute? = locateLive(lease)?.entry?.route

    internal fun beginRecovery(lease: ProtectedRouteLease): ProtectedRouteRecovery? {
        if (!owns(lease)) return null
        val firstObservation = runCatching(clock).getOrNull() ?: run {
            retire(lease)
            return null
        }
        while (true) {
            val located = locateLive(lease) ?: return null
            val entry = located.entry
            val generation = runCatching { lease.session.connectionInfo.value.generation }.getOrDefault(0)
            val previous = entry.recovery
            val connectionState = lease.session.state.value
            if (previous != null &&
                (previous.generation == generation || connectionState == ConnectionState.Reconnecting)
            ) return previous.token
            // onWillReconnect is synchronous BEFORE publishing Reconnecting. A missed precommit
            // callback must not mint a fresh grace window later from a Reconnecting observation.
            if (connectionState != ConnectionState.Connected) {
                if (removeExact(located.snapshot, entry)) return null
                continue
            }
            val recovery = Recovery(
                token = ProtectedRouteRecovery(),
                startedAtMillis = previous?.startedAtMillis ?: firstObservation,
                generation = generation
            )
            // A second loss can follow rearm before the previous completion callback arrives. Give it
            // a new opaque token, but inherit the old deadline until a completion actually commits.
            val nextEntry = Entry(lease, entry.route, entry.generation, recovery)
            if (invalidReason(nextEntry) != null) {
                if (removeExact(located.snapshot, entry)) return null
                continue
            }
            val next = located.snapshot.next(entries = located.snapshot.entries + (lease.peerId to nextEntry))
            if (state.compareAndSet(located.snapshot, next)) {
                return recovery.token.takeIf { lease.finishedStatus() == null }
            }
        }
    }

    internal fun recovered(
        lease: ProtectedRouteLease,
        token: ProtectedRouteRecovery?,
        route: OutboundRoute?
    ): ProtectedRouteStatus {
        if (!owns(lease)) return ProtectedRouteStatus.Retired
        if (token == null) return lease.status
        while (true) {
            val located = locateLive(lease) ?: return lease.status
            val entry = located.entry
            val recovery = entry.recovery ?: return lease.status
            // Old/counterfeit completions are observations only: not even their null route may
            // remove a successor episode. A token is valid only for the exact current map entry.
            if (recovery.token !== token) return lease.status
            val generation = runCatching { lease.session.connectionInfo.value.generation }.getOrDefault(0)
            if (lease.session.state.value != ConnectionState.Connected ||
                recovery.generation == Long.MAX_VALUE || generation != recovery.generation + 1
            ) return lease.status
            val nextEntry = route?.let { Entry(lease, it, generation) }
            if (nextEntry == null || invalidReason(nextEntry) != null || recoveryExpired(lease, recovery)) {
                if (removeExact(located.snapshot, entry)) return lease.status
                continue
            }
            val next = located.snapshot.next(entries = located.snapshot.entries + (lease.peerId to nextEntry))
            if (state.compareAndSet(located.snapshot, next)) return lease.status
        }
    }

    private fun owns(lease: ProtectedRouteLease): Boolean = lease.belongsTo(this, provenance)

    private fun locateLive(lease: ProtectedRouteLease): Located? {
        if (!owns(lease)) return null
        while (true) {
            if (lease.finishedStatus() != null) return null
            val current = state.load()
            if (current.closed) {
                lease.finish(ProtectedRouteStatus.Retired)
                return null
            }
            val entry = current.entries[lease.peerId]?.takeIf { it.lease === lease } ?: return null
            if (invalidReason(entry) != null) {
                if (removeExact(current, entry)) return null
                continue
            }
            if (state.load() !== current) continue
            if (lease.finishedStatus() != null) return null
            return Located(current, entry)
        }
    }

    private fun invalidReason(entry: Entry, installing: Boolean = false): ProtectedRouteStatus? {
        val lease = entry.lease
        lease.finishedStatus()?.let { return it }
        return try {
            val identity = lease.session.peerIdentity
            if (identity.fingerprint == null || identity != lease.identity ||
                identity.peerId != lease.peerId || lease.session.peer.id != lease.peerId ||
                lease.session.admission != PeerAdmission.Trusted || !lease.isAuthorized()
            ) {
                if (installing) ProtectedRouteStatus.NotAuthorized else ProtectedRouteStatus.Retired
            } else if (!lease.isRegistered()) {
                ProtectedRouteStatus.Retired
            } else if (entry.route.transport !== lease.originalTransport ||
                entry.route.transport.type != lease.transportKind || !entry.route.isCurrent
            ) {
                if (installing) ProtectedRouteStatus.Unsupported else ProtectedRouteStatus.Retired
            } else {
                val connectionState = lease.session.state.value
                val generation = lease.session.connectionInfo.value.generation
                val recovery = entry.recovery
                val stateMatches = if (recovery == null) {
                    connectionState == ConnectionState.Connected && generation == entry.generation
                } else {
                    // rearmWith publishes generation before Connected. Observers may see gen+1 /
                    // Reconnecting, or read these two flows across that publication. Retain only the
                    // SAME token/deadline through it; this is not successful completion or new grace.
                    (connectionState == ConnectionState.Connected ||
                        connectionState == ConnectionState.Reconnecting) &&
                        (generation == recovery.generation ||
                            (recovery.generation != Long.MAX_VALUE && generation == recovery.generation + 1))
                }
                if (generation <= 0 || !stateMatches ||
                    (recovery != null && recoveryExpired(lease, recovery))
                ) ProtectedRouteStatus.Retired else null
            }
        } catch (_: Throwable) {
            // A throwing authorization/generation/provider query is not approval to retain a route.
            if (installing) ProtectedRouteStatus.NotAuthorized else ProtectedRouteStatus.Retired
        }
    }

    private fun recoveryExpired(lease: ProtectedRouteLease, recovery: Recovery): Boolean = try {
        val elapsed = clock() - recovery.startedAtMillis
        elapsed < 0 || elapsed >= lease.recoveryGraceMillis
    } catch (_: Throwable) {
        true
    }

    private fun prune(current: Snapshot): Boolean {
        val stale = current.entries.values.filter { invalidReason(it) != null }
        if (stale.isEmpty()) return false
        val next = current.next(entries = current.entries - stale.map { it.lease.peerId }.toSet())
        if (state.compareAndSet(current, next)) {
            stale.forEach { it.lease.finish(ProtectedRouteStatus.Retired) }
            stale.forEach { notifyRetired(it.lease) }
        }
        return true
    }

    private fun removeExact(current: Snapshot, entry: Entry): Boolean {
        if (current.entries[entry.lease.peerId] !== entry) return false
        if (!state.compareAndSet(current, current.next(entries = current.entries - entry.lease.peerId))) return false
        entry.lease.finish(ProtectedRouteStatus.Retired)
        notifyRetired(entry.lease)
        return true
    }

    private fun notifyRetired(lease: ProtectedRouteLease) {
        if (lease.claimRetirementNotification()) runCatching { onRetired(lease) }
    }

    // Ordinary classes intentionally use identity equality; providers cannot introduce CAS ABA via
    // a custom equals(), and even equal empty maps are separated by a fresh version/snapshot object.
    private class Snapshot(
        val version: Long = 0,
        val closed: Boolean = false,
        val entries: Map<PeerId, Entry> = emptyMap()
    ) {
        fun next(closed: Boolean = this.closed, entries: Map<PeerId, Entry> = this.entries): Snapshot =
            Snapshot(version + 1, closed, entries)
    }

    private class Entry(
        val lease: ProtectedRouteLease,
        val route: OutboundRoute,
        val generation: Long,
        val recovery: Recovery? = null
    )

    private class Recovery(val token: ProtectedRouteRecovery, val startedAtMillis: Long, val generation: Long)
    private class Located(val snapshot: Snapshot, val entry: Entry)
}

/** One setup transaction's one-shot candidate, then the exact registered session's retained lease. */
@OptIn(ExperimentalAtomicApi::class)
internal class ProtectedRouteLease internal constructor(
    private val owner: ProtectedRoutes,
    private val provenance: Any,
    val session: P2pSession,
    route: OutboundRoute,
    internal val isAuthorized: () -> Boolean,
    internal val isRegistered: () -> Boolean,
    internal val recoveryGraceMillis: Long
) {
    internal val peerId = session.peer.id
    internal val identity = session.peerIdentity
    internal val originalTransport = route.transport
    val transportKind = originalTransport.type
    private val candidate = AtomicReference<OutboundRoute?>(route)
    private val terminal = AtomicReference<ProtectedRouteStatus?>(null)
    private val retirementNotified = AtomicBoolean(false)

    val status: ProtectedRouteStatus get() = owner.statusOf(this)
    fun routeForUse(): OutboundRoute? = owner.routeForUse(this)
    fun beginRecovery(): ProtectedRouteRecovery? = owner.beginRecovery(this)
    fun recovered(token: ProtectedRouteRecovery?, route: OutboundRoute?): ProtectedRouteStatus =
        owner.recovered(this, token, route)

    internal fun belongsTo(manager: ProtectedRoutes, seal: Any): Boolean = owner === manager && provenance === seal
    internal fun takeCandidate(): OutboundRoute? = candidate.exchange(null)
    internal fun finishedStatus(): ProtectedRouteStatus? = terminal.load()
    internal fun finish(reason: ProtectedRouteStatus): ProtectedRouteStatus {
        terminal.compareAndSet(null, reason)
        candidate.exchange(null)
        return terminal.load() ?: reason
    }

    internal fun claimRetirementNotification(): Boolean = retirementNotified.compareAndSet(false, true)
}

/** Identity-only completion proof: an old episode cannot refresh or clear a later episode. */
internal class ProtectedRouteRecovery
