package dev.p2pkit.rpc

/** Call-level attempts include the initial invocation and subsequent status/reinvocation attempts. */
public sealed class RpcRetry(public val maxAttempts: Int) {
    init { require(maxAttempts in 1..3) }

    /** Recover retained results, but NEVER re-execute after ambiguous transmission. */
    public class RecoverOnly(maxAttempts: Int = 3) : RpcRetry(maxAttempts)

    /** Also requires the procedure descriptor's explicit Idempotent promise. */
    public class Idempotent(maxAttempts: Int = 3) : RpcRetry(maxAttempts)
}

/** Upper bounds, not qualified performance. Values may be lowered but never exceed the approved profile. */
public class RpcLimits(
    public val trustedClients: Int = 128,
    public val runningCalls: Int = 128,
    public val queuedCalls: Int = 256,
    public val callsPerClient: Int = 8,
    public val payloadBytes: Long = 64L * 1_048_576,
    public val resultCacheBytes: Long = 32L * 1_048_576,
    public val recordsPerClient: Int = 1_024,
    public val totalRecords: Int = 131_072,
) {
    init {
        require(trustedClients in 1..128 && runningCalls in 1..128 && queuedCalls in 0..256)
        require(callsPerClient in 1..8)
        require(payloadBytes in 1..(64L * 1_048_576))
        require(resultCacheBytes in 0..minOf(payloadBytes, 32L * 1_048_576))
        require(recordsPerClient in 1..1_024 && totalRecords in 1..131_072)
    }

    public companion object {
        /** Required qualification is still separate on each actual host platform. */
        public fun host128(): RpcLimits = RpcLimits()
    }
}

public enum class RpcFailureKind {
    NotConnected, Closed, PermissionMissing, Overloaded, DeadlineExceeded, Unauthorized, Authentication,
    Protocol, IncompatibleVersion, UnknownProcedure, InvalidPayload, HandlerFailed,
    ResultUnavailable, UnknownOutcome, HostRestarted, RemoteCancelled, TrustStorage,
}

public enum class RpcFailurePhase { Encoding, Admission, Negotiation, Sending, AwaitingResponse, Decoding, Trust }
public enum class RpcExecutionEvidence { NotSent, RejectedBeforeExecution, MayHaveExecuted, HandlerFinished }
public enum class RpcRetryAdvice { Never, SafeBeforeExecution, RecoverStatus, ApplicationIdempotencyRequired }

/** Intentionally contains no nested exception, payload, stack trace text, endpoint, or remote reason. */
public class RpcFailure(
    public val kind: RpcFailureKind,
    public val phase: RpcFailurePhase,
    public val requestId: RpcRequestId? = null,
    public val executionEvidence: RpcExecutionEvidence = RpcExecutionEvidence.NotSent,
    public val retryAdvice: RpcRetryAdvice = RpcRetryAdvice.Never,
) : Exception("RPC ${kind.name} (${phase.name}; ${executionEvidence.name})")

public enum class RpcConnectionState {
    Disconnected, Connecting, Negotiating, Pairing, Ready, Reconnecting, Closed, Failed,
}
public enum class RpcNotifyResult { Enqueued, NotConnected, NotAuthorized, DroppedAtCapacity }

/** Bounded counters only. No payloads, pins, invitation text, or automatic diagnostic export. */
public data class RpcDiagnostics(
    public val acceptedCalls: Long = 0,
    public val completedCalls: Long = 0,
    public val refusedCalls: Long = 0,
    public val duplicateRequests: Long = 0,
    public val droppedNotifications: Long = 0,
    public val protocolFailures: Long = 0,
    public val connectionFailures: Long = 0,
    public val runningCalls: Int = 0,
    public val queuedCalls: Int = 0,
    public val retainedRecords: Int = 0,
    public val retainedPayloadBytes: Long = 0,
)
