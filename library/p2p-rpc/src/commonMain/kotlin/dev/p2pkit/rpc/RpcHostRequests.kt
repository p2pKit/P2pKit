package dev.p2pkit.rpc

/** Host-local execution state, never a guarantee of delivery to the client. */
public enum class RpcHostCallState { Queued, Running, Succeeded, BusinessError, Failed, Cancelled, TimedOut, Refused }

/** Exact admitted logical-call totals for one runtime lifetime; retries/status requests do not count twice. */
public data class RpcRequestTotals(
    public val accepted: Long = 0,
    public val succeeded: Long = 0,
    public val businessErrors: Long = 0,
    public val failed: Long = 0,
    public val cancelled: Long = 0,
    public val timedOut: Long = 0,
    /** Host rejected INVOKE attempts, or client calls refused locally before admission; not admitted calls. */
    public val refusedAttempts: Long = 0,
)

/**
 * Explicit local administrator inspection. Contains authenticated peer identity and request metadata, NO payload.
 * Do not automatically log/export it. Revision identifies an observation, not another execution or wire attempt.
 */
public class RpcHostCallEntry internal constructor(
    public val revision: Long,
    /** Stable local capture identity; unlike wire IDs it also distinguishes post-retention ID reuse. */
    public val captureId: Long,
    public val requestId: String,
    public val peerFingerprint: String,
    public val procedure: String,
    public val version: Int,
    public val state: RpcHostCallState,
    public val elapsedMillis: Long,
    public val failure: RpcFailureKind?,
    public val executionEvidence: RpcExecutionEvidence?,
    public val admitted: Boolean,
) {
    override fun toString(): String = "RpcHostCallEntry(private metadata omitted)"
}

/** Bounded current/terminal history. Capture loss never rejects an RPC; totals remain independent of capture. */
public class RpcHostRequests internal constructor(
    public val hostIncarnation: String,
    public val revision: Long,
    entries: List<RpcHostCallEntry>,
    public val totals: RpcRequestTotals,
    public val droppedCaptures: Long,
    /** Conservative metadata allowance charged to the SAME existing host payload budget. */
    public val retainedMetadataBytes: Long,
) {
    private val retainedEntries = entries.toList()
    public val entries: List<RpcHostCallEntry> get() = retainedEntries.toList()
    override fun toString(): String = "RpcHostRequests(private metadata omitted)"
}
