package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcExecutionEvidence
import kotlinx.coroutines.flow.MutableStateFlow

public enum class RpcRequestSide { Host, Client }
public enum class RpcRequestOutcome { Running, Succeeded, BusinessError, RpcError, Cancelled, TimedOut, LocalError }

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
) {
    /** No application payload, peer identity or request ID. Explicit details export is separate. */
    public fun diagnostics(): String =
        "$side $procedure/v$version: $outcome; error=${errorCode ?: "none"}; elapsedMs=$elapsedMillis; " +
            "evidence=${executionEvidence?.name ?: "Unknown"}"

    public fun details(): String = diagnostics() + "\nRequest ID: ${requestId ?: "not available"}" +
        "\nPeer fingerprint: ${peerFingerprint ?: "not available"}" +
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
    )
    private val current = MutableStateFlow(Snapshot())

    public val revision: Long get() = current.value.revision
    /** Capture loss is visible; it must not be confused with a refused RPC or an exact total-request count. */
    public val droppedCaptures: Long get() = current.value.dropped
    public fun entries(): List<RpcRequestEntry> = current.value.entries.toList()

    internal fun begin(
        side: RpcRequestSide, procedure: String, version: Int, requestPreview: String,
        requestId: String? = null, peerFingerprint: String? = null,
    ): Long? {
        require(procedure.length in 1..96 && version in 1..65_535)
        require(requestId == null || requestId.length <= 64)
        require(peerFingerprint == null || peerFingerprint.length <= 128)
        val preview = boundedRpcPreview(requestPreview)
        while (true) {
            val before = current.value
            val entries = before.entries.toMutableList()
            val terminal = entries.indexOfFirst { it.outcome != RpcRequestOutcome.Running }
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
                preview, "", RpcRequestOutcome.Running, null, 0, null)
            if (current.compareAndSet(before, Snapshot(
                    before.next + 1, before.revision + 1, entries.toList(), before.dropped,
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
        require(outcome != RpcRequestOutcome.Running && elapsedMillis >= 0)
        require(errorCode == null || (errorCode.length in 1..96 && errorCode.all { it.isLetterOrDigit() || it == '.' }))
        require(requestId == null || requestId.length <= 64)
        val preview = boundedRpcPreview(responsePreview)
        while (true) {
            val before = current.value
            val entry = before.entries.firstOrNull { it.localId == localId } ?: return
            if (entry.outcome != RpcRequestOutcome.Running) return // First terminal observation wins.
            val updated = RpcRequestEntry(entry.localId, entry.side, entry.procedure, entry.version,
                requestId ?: entry.requestId, entry.peerFingerprint, entry.requestPreview, preview, outcome,
                errorCode, elapsedMillis, evidence)
            val after = before.copy(revision = before.revision + 1,
                entries = before.entries.map { if (it.localId == localId) updated else it })
            if (current.compareAndSet(before, after)) return
        }
    }

    /** Explicit privacy action; running operations keep their entries until they finish. IDs are never recycled. */
    public fun clearCompleted() {
        while (true) {
            val before = current.value
            if (current.compareAndSet(before, before.copy(
                    revision = before.revision + 1,
                    entries = before.entries.filter { it.outcome == RpcRequestOutcome.Running },
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
