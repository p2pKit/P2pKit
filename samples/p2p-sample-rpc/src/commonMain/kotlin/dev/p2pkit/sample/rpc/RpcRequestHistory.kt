package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcHostCallState
import dev.p2pkit.rpc.RpcHostRequests
import kotlinx.coroutines.flow.MutableStateFlow

public enum class RpcRequestSide { Host, Client }
public enum class RpcRequestOutcome {
    Queued, Running, Succeeded, BusinessError, RpcError, Cancelled, TimedOut, LocalError,
}

/** App-owned, explicitly viewed data; never part of RpcDiagnostics or automatic diagnostic export. */
public class RpcRequestEntry internal constructor(
    public val localId: Long,
    public val side: RpcRequestSide,
    public val procedure: String,
    public val version: Int,
    public val requestId: String?,
    public val peerFingerprint: String?,
    public val requestPreview: String,
    public val responsePreview: String,
    public val outcome: RpcRequestOutcome,
    public val errorCode: String?,
    public val elapsedMillis: Long,
    public val executionEvidence: RpcExecutionEvidence?,
    public val hostIncarnation: String? = null,
    internal val refusedRevision: Long? = null,
    public val hostCaptureId: Long? = null,
) {
    /** No application payload, peer identity or request ID. Explicit details export is separate. */
    public fun diagnostics(): String =
        "$side $procedure/v$version: $outcome; error=${errorCode ?: "none"}; elapsedMs=$elapsedMillis; " +
            "evidence=${executionEvidence?.name ?: "Unknown"}"

    public fun details(): String = diagnostics() + "\nRequest ID: ${requestId ?: "not available"}" +
        "\nPeer fingerprint: ${peerFingerprint ?: "not available"}" +
        "\nHost lifetime: ${hostIncarnation ?: "not available"}" +
        "\nObservation: ${if (refusedRevision == null) "logical call" else "refused invocation attempt"}" +
        "\nRequest preview: $requestPreview\nResponse preview: $responsePreview"

    override fun toString(): String = "RpcRequestEntry(application data omitted)"
}

/**
 * In-memory UI history, separate from live engine counters and result recovery. Retain the owner across Stop.
 * At most 256 entries, each with two <=1024-byte previews. Active entries are never silently evicted.
 * When all slots are active, capture is declined (not the RPC); no extra unbounded queue is created.
 */
public class RpcRequestHistory(maxEntries: Int = 100) {
    private val capacity = maxEntries.also { require(it in 1..256) }
    private data class Snapshot(
        val next: Long = 1, val revision: Long = 0, val entries: List<RpcRequestEntry> = emptyList(),
        val dropped: Long = 0,
        val hostCursor: String? = null, val hostRevision: Long = 0,
    )
    private val current = MutableStateFlow(Snapshot())

    public val revision: Long get() = current.value.revision
    /** Capture loss is visible; it must not be confused with a refused RPC or an exact total-request count. */
    public val droppedCaptures: Long get() = current.value.dropped
    public fun entries(): List<RpcRequestEntry> = current.value.entries.toList()

    internal fun begin(
        side: RpcRequestSide, procedure: String, version: Int, requestPreview: String,
        requestId: String? = null, peerFingerprint: String? = null, hostIncarnation: String? = null,
        hostCaptureId: Long? = null,
    ): Long? {
        require(procedure.length in 1..96 && version in 1..65_535)
        require(requestId == null || requestId.length <= 64)
        require(peerFingerprint == null || peerFingerprint.length <= 128)
        val preview = boundedRpcPreview(requestPreview)
        while (true) {
            val before = current.value
            val entries = before.entries.toMutableList()
            // A handler can enter after the live sampler has already captured its queued metadata.
            val existing = entries.firstOrNull { hostIncarnation != null && it.hostIncarnation == hostIncarnation &&
                it.refusedRevision == null && it.requestId == requestId && it.peerFingerprint == peerFingerprint &&
                it.hostCaptureId == hostCaptureId }
            if (existing != null) {
                if (!active(existing.outcome)) return existing.localId
                val updated = RpcRequestEntry(existing.localId, side, procedure, version, requestId, peerFingerprint,
                    preview, existing.responsePreview, RpcRequestOutcome.Running, existing.errorCode,
                    existing.elapsedMillis, existing.executionEvidence, hostIncarnation, hostCaptureId = hostCaptureId)
                if (current.compareAndSet(before, before.copy(revision = before.revision + 1,
                        entries = entries.map { if (it === existing) updated else it }))) return existing.localId
                continue
            }
            val terminal = entries.indexOfFirst { !active(it.outcome) }
            if (before.next == Long.MAX_VALUE || (entries.size == capacity && terminal < 0)) {
                val dropped = if (before.dropped == Long.MAX_VALUE) before.dropped else before.dropped + 1
                if (current.compareAndSet(before, before.copy(revision = before.revision + 1, dropped = dropped))) {
                    return null
                }
                continue
            }
            if (entries.size == capacity) {
                entries.removeAt(terminal)
            }
            entries += RpcRequestEntry(before.next, side, procedure, version, requestId, peerFingerprint,
                preview, "", RpcRequestOutcome.Running, null, 0, null, hostIncarnation, hostCaptureId = hostCaptureId)
            if (current.compareAndSet(before, before.copy(
                    next = before.next + 1, revision = before.revision + 1, entries = entries.toList(),
                ))) {
                return before.next
            }
        }
    }

    internal fun finish(
        localId: Long?, outcome: RpcRequestOutcome, elapsedMillis: Long,
        responsePreview: String = "", errorCode: String? = null,
        requestId: String? = null, evidence: RpcExecutionEvidence? = null,
    ) {
        if (localId == null) return
        require(!active(outcome) && elapsedMillis >= 0)
        require(errorCode == null || (errorCode.length in 1..96 && errorCode.all { it.isLetterOrDigit() || it == '.' }))
        require(requestId == null || requestId.length <= 64)
        val preview = boundedRpcPreview(responsePreview)
        while (true) {
            val before = current.value
            val entry = before.entries.firstOrNull { it.localId == localId } ?: return
            if (!active(entry.outcome)) return // First terminal observation wins.
            val updated = RpcRequestEntry(entry.localId, entry.side, entry.procedure, entry.version,
                requestId ?: entry.requestId, entry.peerFingerprint, entry.requestPreview, preview, outcome,
                errorCode, elapsedMillis, evidence, entry.hostIncarnation, entry.refusedRevision, entry.hostCaptureId)
            val after = before.copy(revision = before.revision + 1,
                entries = before.entries.map { if (it.localId == localId) updated else it })
            if (current.compareAndSet(before, after)) return
        }
    }

    internal fun captureOmitted() {
        while (true) {
            val before = current.value
            val dropped = if (before.dropped == Long.MAX_VALUE) before.dropped else before.dropped + 1
            if (current.compareAndSet(before, before.copy(dropped = dropped, revision = before.revision + 1))) return
        }
    }

    /** Handler data is not an engine terminal result. Encoding/cancellation can still fail after this point. */
    internal fun hostResponse(localId: Long?, response: String, errorCode: String? = null) {
        if (localId == null) return
        val preview = boundedRpcPreview(response)
        while (true) {
            val before = current.value
            val entry = before.entries.firstOrNull { it.localId == localId && active(it.outcome) } ?: return
            val updated = RpcRequestEntry(entry.localId, entry.side, entry.procedure, entry.version, entry.requestId,
                entry.peerFingerprint, entry.requestPreview, preview, entry.outcome, errorCode,
                entry.elapsedMillis, entry.executionEvidence, entry.hostIncarnation, entry.refusedRevision,
                entry.hostCaptureId)
            if (current.compareAndSet(before, before.copy(revision = before.revision + 1,
                    entries = before.entries.map { if (it === entry) updated else it }))) return
        }
    }

    internal fun observeHost(observation: RpcHostRequests) {
        val snapshot = current.value
        if (snapshot.hostCursor == observation.hostIncarnation && observation.revision <= snapshot.hostRevision) return
        observeHost(observation.hostIncarnation, observation.revision, observation.entries.map { row ->
            val outcome = when (row.state) {
                RpcHostCallState.Queued -> RpcRequestOutcome.Queued
                RpcHostCallState.Running -> RpcRequestOutcome.Running
                RpcHostCallState.Succeeded -> RpcRequestOutcome.Succeeded
                RpcHostCallState.BusinessError -> RpcRequestOutcome.BusinessError
                RpcHostCallState.Cancelled -> RpcRequestOutcome.Cancelled
                RpcHostCallState.TimedOut -> RpcRequestOutcome.TimedOut
                else -> RpcRequestOutcome.RpcError
            }
            RpcRequestEntry(row.revision, RpcRequestSide.Host, row.procedure, row.version,
                row.requestId, row.peerFingerprint, "", "", outcome, row.failure?.name, row.elapsedMillis,
                row.executionEvidence, observation.hostIncarnation, if (row.admitted) null else row.revision,
                row.captureId)
        })
    }

    /** Internal normalized observations keep library-owned metadata constructors out of sample tests. */
    internal fun observeHost(incarnation: String, revision: Long, rows: List<RpcRequestEntry>) {
        while (true) {
            val before = current.value
            val previousRevision = if (before.hostCursor == incarnation) before.hostRevision else 0
            if (revision <= previousRevision) return
            val entries = before.entries.toMutableList()
            var next = before.next
            var dropped = before.dropped
            for (row in rows.filter { it.localId > previousRevision }) {
                val existing = entries.firstOrNull { it.hostIncarnation == incarnation &&
                    it.requestId == row.requestId && it.peerFingerprint == row.peerFingerprint &&
                    it.refusedRevision == row.refusedRevision && it.hostCaptureId == row.hostCaptureId }
                if (existing != null && !active(existing.outcome)) continue // First engine terminal wins.
                val outcome = if (existing?.outcome == RpcRequestOutcome.Running &&
                    row.outcome == RpcRequestOutcome.Queued) RpcRequestOutcome.Running else row.outcome
                if (existing == null) {
                    val terminal = entries.indexOfFirst { !active(it.outcome) }
                    if (next == Long.MAX_VALUE || (entries.size == capacity && terminal < 0)) {
                        if (dropped < Long.MAX_VALUE) dropped++
                        continue
                    }
                    if (entries.size == capacity) entries.removeAt(terminal)
                }
                val updated = RpcRequestEntry(existing?.localId ?: next++, RpcRequestSide.Host, row.procedure,
                    row.version, row.requestId, row.peerFingerprint,
                    existing?.requestPreview ?: "[request not captured by application handler]",
                    existing?.responsePreview ?: "[response not captured by application handler]",
                    outcome, row.errorCode ?: existing?.errorCode, row.elapsedMillis, row.executionEvidence,
                    incarnation, row.refusedRevision, row.hostCaptureId)
                if (existing == null) entries += updated else entries[entries.indexOf(existing)] = updated
            }
            val after = before.copy(next = next, revision = before.revision + 1, entries = entries.toList(),
                dropped = dropped, hostCursor = incarnation, hostRevision = revision)
            if (current.compareAndSet(before, after)) return
        }
    }

    /** Stop cannot prove rollback or manufacture a terminal response missed by the local sampler. */
    internal fun retireHost(incarnation: String) {
        for (entry in entries()) {
            if (entry.hostIncarnation == incarnation && active(entry.outcome)) {
                finish(entry.localId, RpcRequestOutcome.LocalError, entry.elapsedMillis,
                    entry.responsePreview, "HostStoppedOutcomeUnobserved",
                    evidence = RpcExecutionEvidence.MayHaveExecuted)
            }
        }
    }

    private fun active(outcome: RpcRequestOutcome): Boolean =
        outcome == RpcRequestOutcome.Queued || outcome == RpcRequestOutcome.Running

    /** Explicit privacy action; running operations keep their entries until they finish. IDs are never recycled. */
    public fun clearCompleted() {
        while (true) {
            val before = current.value
            if (current.compareAndSet(before, before.copy(
                    revision = before.revision + 1,
                    entries = before.entries.filter { active(it.outcome) },
                ))) return
        }
    }
}

/** Bounded allocation even when input is huge. Never split a UTF-16 surrogate pair or UTF-8 character. */
internal fun boundedRpcPreview(value: String): String {
    val suffix = "\n[preview truncated]"
    val bytes = value.take(1_025).encodeToByteArray()
    if (value.length <= 1_024 && bytes.size <= 1_024) return value
    val budget = 1_024 - suffix.encodeToByteArray().size
    var end = minOf(budget, bytes.size)
    while (end > 0 && end < bytes.size && (bytes[end].toInt() and 0xc0) == 0x80) end--
    return bytes.decodeToString(endIndex = end) + suffix
}
