package dev.p2pkit.rpc

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/** Queued refers only to the local transport send queue, never a guess about a remote handler. */
public enum class RpcCallStage {
    Created, Encoding, Queued, Sending, AwaitingResponse, Recovering,
    Succeeded, BusinessError, Failed, Cancelled, TimedOut,
}

/** One bounded metadata snapshot. No request/response data, addresses, nested errors, or automatic export. */
public class RpcCallProgress internal constructor(
    public val stage: RpcCallStage,
    public val requestId: String?,
    public val peerFingerprint: String?,
    public val hostIncarnation: String?,
    public val elapsedMillis: Long,
    public val executionEvidence: RpcExecutionEvidence,
    public val failureKind: RpcFailureKind?,
    public val failurePhase: RpcFailurePhase?,
) {
    override fun toString(): String = "RpcCallProgress(private metadata omitted)"
}

/**
 * Caller-owned, single-use observation for callWithObservation. No timer, callback, queue or coroutine of its own.
 * State is conflated; a UI may miss intermediate stages. Inspect explicitly and discard with the owning request.
 */
public class RpcCallObservation {
    private val claimed = MutableStateFlow(false)
    private val mutable = MutableStateFlow(RpcCallProgress(RpcCallStage.Created, null, null, null, 0,
        RpcExecutionEvidence.NotSent, null, null))
    public val progress: kotlinx.coroutines.flow.StateFlow<RpcCallProgress> = mutable.asStateFlow()

    internal fun claim() {
        check(claimed.compareAndSet(false, true)) { "An RPC observation belongs to exactly one call" }
        change(RpcCallStage.Encoding, 0, RpcExecutionEvidence.NotSent)
    }

    internal fun identify(id: String, peer: String, incarnation: String) {
        mutable.update {
            if (terminal(it.stage) || it.requestId != null) it else RpcCallProgress(
                it.stage, id, peer, incarnation, it.elapsedMillis,
                it.executionEvidence, it.failureKind, it.failurePhase)
        }
    }

    internal fun change(
        stage: RpcCallStage, elapsed: Long, evidence: RpcExecutionEvidence,
        failure: RpcFailureKind? = null, phase: RpcFailurePhase? = null,
    ) {
        mutable.update {
            if (terminal(it.stage)) it else RpcCallProgress(stage, it.requestId, it.peerFingerprint,
                it.hostIncarnation, elapsed.coerceAtLeast(it.elapsedMillis), evidence, failure, phase)
        }
    }

    private fun terminal(stage: RpcCallStage): Boolean = when (stage) {
        RpcCallStage.Succeeded, RpcCallStage.BusinessError, RpcCallStage.Failed,
        RpcCallStage.Cancelled, RpcCallStage.TimedOut -> true
        else -> false
    }
}
