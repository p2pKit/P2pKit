package dev.p2pkit.rpc

import dev.p2pkit.core.PeerIdentity
import kotlinx.serialization.KSerializer

/** Idempotent is an application promise, not storage/transaction support supplied by RPC. */
public enum class RpcRetrySafety { NeverReinvoke, Idempotent }

/** Shared, explicit schema. Change version when changing an incompatible application contract. */
public class RpcProcedure<Request, Response, ApplicationError>(
    public val name: String,
    public val version: Int,
    public val request: KSerializer<Request>,
    public val response: KSerializer<Response>,
    public val applicationError: KSerializer<ApplicationError>,
    public val retrySafety: RpcRetrySafety = RpcRetrySafety.NeverReinvoke,
    public val requestLimitBytes: Int = 65_536,
    public val responseLimitBytes: Int = 65_536,
    public val errorLimitBytes: Int = 65_536,
) {
    init {
        validateRpcName(name, version)
        require(listOf(requestLimitBytes, responseLimitBytes, errorLimitBytes).all { it in 1..1_048_576 })
    }

    internal val key: String get() = "$name/$version"
    override fun toString(): String = "RpcProcedure($key)"
}

/** Explicit typed best-effort update. No subscriptions, remote handlers, replay, or durability. */
public class RpcNotification<T>(
    public val name: String,
    public val version: Int,
    public val payload: KSerializer<T>,
    public val limitBytes: Int = 16_384,
) {
    init {
        validateRpcName(name, version)
        require(limitBytes in 1..16_384)
    }

    internal val key: String get() = "$name/$version"
}

/** Business errors are normal typed replies, never confused with infrastructure failure. */
public sealed class RpcReply<out Response, out ApplicationError> {
    public data class Success<Response>(public val value: Response) : RpcReply<Response, Nothing>()
    public data class ApplicationError<E>(public val error: E) : RpcReply<Nothing, E>()
}

/** Stable random logical request identity, allocated by the client and reused during bounded recovery. */
public class RpcRequestId internal constructor(public val value: String) {
    override fun equals(other: Any?): Boolean = other is RpcRequestId && other.value == value
    override fun hashCode(): Int = value.hashCode()
    override fun toString(): String = value
}

/**
 * A decoded terminal reply and its actual wire request identity. A business error is still a completed reply.
 * Elapsed time is measured locally and includes bounded recovery, not just remote handler execution.
 * This object contains application data; do not put it in diagnostics automatically.
 */
public class RpcCallDetails<out Response, out ApplicationError> internal constructor(
    public val requestId: RpcRequestId,
    public val reply: RpcReply<Response, ApplicationError>,
    public val elapsedMillis: Long,
) {
    public val executionEvidence: RpcExecutionEvidence get() = RpcExecutionEvidence.HandlerFinished
    override fun toString(): String = "RpcCallDetails(application data omitted)"
}

/** Identity comes exclusively from the authenticated session, never a request-body claim. */
public class RpcCallContext internal constructor(
    public val peer: PeerIdentity,
    public val requestId: RpcRequestId,
    /** Remaining host-local allowance at handler start; duplicates never extend it. */
    public val remainingMillis: Long,
)

internal fun validateRpcName(name: String, version: Int) {
    require(name.length in 1..96 && name.first() in 'a'..'z' &&
        name.all { it in 'a'..'z' || it in '0'..'9' || it in ".-" }) { "Invalid RPC procedure/notification name" }
    require(version in 1..65_535)
}
