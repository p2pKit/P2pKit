package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PayloadLease
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcHostCallEntry
import dev.p2pkit.rpc.RpcHostCallState
import dev.p2pkit.rpc.RpcHostRequests
import dev.p2pkit.rpc.RpcRequestTotals
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

/** All mutation under the engine mutex. Bounded <=256 scan, no callbacks, decode, I/O or dedup-table scan. */
internal class RpcHostRequestRecorder(
    private val capacity: Int, private val budget: PayloadBudget, private val incarnation: String,
) {
    init { require(capacity in 0..256) }
    private val leases = mutableListOf<PayloadLease>()
    private var closed = false
    private val mutable = MutableStateFlow(RpcHostRequests(incarnation, 0, emptyList(), RpcRequestTotals(), 0, 0))
    val state = mutable.asStateFlow()

    fun accept(id: String, peer: String, name: String, version: Int, queued: Boolean): Long? {
        val before = mutable.value
        publish(before.totals.copy(accepted = increment(before.totals.accepted)))
        return insert(id, peer, name, version, if (queued) RpcHostCallState.Queued else RpcHostCallState.Running,
            0, null, null, true)
    }

    fun running(id: String, peer: String, elapsed: Long) {
        update(id, peer, RpcHostCallState.Running, elapsed, null, null)
    }

    /** The engine calls exactly once at its first terminal commit, even when history capture was declined. */
    fun finish(id: String, peer: String, kind: WireKind, code: Int, elapsed: Long) {
        val reason = if (kind == WireKind.Failure) WireFailure.entries.first { it.code == code } else null
        val outcome = when {
            kind == WireKind.Success -> RpcHostCallState.Succeeded
            kind == WireKind.ApplicationError -> RpcHostCallState.BusinessError
            reason?.kind == RpcFailureKind.DeadlineExceeded -> RpcHostCallState.TimedOut
            reason?.kind == RpcFailureKind.RemoteCancelled -> RpcHostCallState.Cancelled
            else -> RpcHostCallState.Failed
        }
        val totals = mutable.value.totals
        publish(when (outcome) {
            RpcHostCallState.Succeeded -> totals.copy(succeeded = increment(totals.succeeded))
            RpcHostCallState.BusinessError -> totals.copy(businessErrors = increment(totals.businessErrors))
            RpcHostCallState.TimedOut -> totals.copy(timedOut = increment(totals.timedOut))
            RpcHostCallState.Cancelled -> totals.copy(cancelled = increment(totals.cancelled))
            else -> totals.copy(failed = increment(totals.failed))
        })
        update(id, peer, outcome, elapsed, reason?.kind, reason?.evidence ?: RpcExecutionEvidence.HandlerFinished)
    }

    fun refuse(id: String, peer: String, name: String, version: Int, reason: WireFailure) {
        val totals = mutable.value.totals
        publish(totals.copy(refusedAttempts = increment(totals.refusedAttempts)))
        // Rejected attempts cannot overwrite the outcome of an earlier admitted call with the same wire ID.
        insert(id, peer, name, version, RpcHostCallState.Refused, 0, reason.kind, reason.evidence, false)
    }

    private fun insert(
        id: String, peer: String, name: String, version: Int, outcome: RpcHostCallState,
        elapsed: Long, failure: RpcFailureKind?, evidence: RpcExecutionEvidence?, admitted: Boolean,
    ): Long? {
        if (capacity == 0 || closed) return null
        val before = mutable.value
        val entries = before.entries.toMutableList()
        val terminal = entries.indexOfFirst { !active(it.state) }
        if (entries.size == capacity && terminal < 0) { dropped(); return null }
        if (entries.size < capacity) {
            val lease = budget.tryReserve(ENTRY_ALLOWANCE) ?: run { dropped(); return null }
            leases += lease
        } else entries.removeAt(terminal)
        entries += RpcHostCallEntry(increment(before.revision), increment(before.revision), id, peer, name, version,
            outcome, elapsed.coerceAtLeast(0), failure, evidence, admitted)
        publish(entries = entries.toList())
        return entries.last().captureId
    }

    private fun update(
        id: String, peer: String, outcome: RpcHostCallState, elapsed: Long,
        failure: RpcFailureKind?, evidence: RpcExecutionEvidence?,
    ) {
        val before = mutable.value
        val entry = before.entries.firstOrNull {
            it.admitted && it.requestId == id && it.peerFingerprint == peer && active(it.state)
        } ?: return
        val updated = RpcHostCallEntry(increment(before.revision), entry.captureId, id, peer, entry.procedure,
            entry.version, outcome, elapsed.coerceAtLeast(0), failure, evidence, true)
        publish(entries = before.entries.map { if (it === entry) updated else it })
    }

    private fun dropped() {
        publish(dropped = increment(mutable.value.droppedCaptures))
    }

    private fun publish(
        totals: RpcRequestTotals = mutable.value.totals,
        entries: List<RpcHostCallEntry> = mutable.value.entries,
        dropped: Long = mutable.value.droppedCaptures,
    ) {
        mutable.value = RpcHostRequests(incarnation, increment(mutable.value.revision), entries,
            totals, dropped, leases.size * ENTRY_ALLOWANCE)
    }

    /** Clear identities before releasing the allowance; late non-cooperative completions update totals only. */
    fun close() {
        closed = true
        publish(entries = emptyList())
        leases.forEach { it.release() }
        leases.clear()
        publish(entries = emptyList())
    }

    private fun active(state: RpcHostCallState): Boolean =
        state == RpcHostCallState.Queued || state == RpcHostCallState.Running

    private fun increment(value: Long): Long = if (value == Long.MAX_VALUE) value else value + 1

    private companion object {
        // <=96 name + 128 pin + 32 ID characters, immutable entries, list/reference overhead and snapshot headroom.
        const val ENTRY_ALLOWANCE: Long = 4_096
    }
}
