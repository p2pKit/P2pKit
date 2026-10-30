package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PayloadLease
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.rpc.RpcAuthorizationContext
import dev.p2pkit.rpc.RpcAuthorizationScope
import dev.p2pkit.rpc.RpcCallContext
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRetrySafety

internal class EncodedReply(val kind: WireKind, val body: OwnedBytes)

internal interface RegisteredProcedure {
    val name: String
    val version: Int
    val key: String get() = "$name/$version"
    val requestLimit: Int
    val resultLimit: Int
    val retrySafety: RpcRetrySafety
    val scoped: Boolean get() = false
    suspend fun authenticate(identity: PeerIdentity, request: OwnedBytes, budget: PayloadBudget): RpcAuthorizationScope? =
        null
    suspend fun authorize(context: RpcAuthorizationContext): Boolean = false
    suspend fun authorize(identity: PeerIdentity): Boolean
    suspend fun execute(
        context: RpcCallContext,
        request: OwnedBytes,
        budget: PayloadBudget,
        decodeAllowance: PayloadLease,
        resultAllowance: PayloadLease,
        beforeHandler: suspend () -> Unit,
    ): EncodedReply
}

internal fun <Q, R, E> registeredProcedure(
    procedure: RpcProcedure<Q, R, E>,
    authorize: suspend (PeerIdentity) -> Boolean,
    handler: suspend (RpcCallContext, Q) -> RpcReply<R, E>,
): RegisteredProcedure = object : RegisteredProcedure {
    override val name: String = procedure.name
    override val version: Int = procedure.version
    override val requestLimit: Int = procedure.requestLimitBytes
    override val resultLimit: Int = maxOf(procedure.responseLimitBytes, procedure.errorLimitBytes)
    override val retrySafety: RpcRetrySafety = procedure.retrySafety
    override suspend fun authorize(identity: PeerIdentity): Boolean = authorize.invoke(identity)

    override suspend fun execute(
        context: RpcCallContext,
        request: OwnedBytes,
        budget: PayloadBudget,
        decodeAllowance: PayloadLease,
        resultAllowance: PayloadLease,
        beforeHandler: suspend () -> Unit,
    ): EncodedReply {
        val decoded = RpcBodyCodec.decode(procedure.request, request, requestLimit, budget, decodeAllowance,
            releaseReservation = context.authorizationScope == null)
        // Scoped execution can suspend in its fresh policy before entering the handler. The host
        // owns its decoding allowance through finalization, not just until JSON parsing returns.
        beforeHandler()
        return when (val reply = handler(context, decoded)) {
            is RpcReply.Success -> EncodedReply(
                WireKind.Success,
                RpcBodyCodec.encode(
                    procedure.response, reply.value, procedure.responseLimitBytes, budget, resultAllowance,
                ),
            )
            is RpcReply.ApplicationError -> EncodedReply(
                WireKind.ApplicationError,
                RpcBodyCodec.encode(
                    procedure.applicationError, reply.error, procedure.errorLimitBytes, budget, resultAllowance,
                ),
            )
        }
    }
}

/** Typed credentials are decoded under a held allowance, even while authentication suspends. */
internal fun <Q, R, E> registeredScopedProcedure(
    procedure: RpcProcedure<Q, R, E>,
    authenticate: suspend (PeerIdentity, Q) -> RpcAuthorizationScope?,
    authorize: suspend (RpcAuthorizationContext) -> Boolean,
    handler: suspend (RpcCallContext, Q) -> RpcReply<R, E>,
): RegisteredProcedure = object : RegisteredProcedure by registeredProcedure(procedure, { false }, handler) {
    override val scoped: Boolean = true
    override suspend fun authorize(context: RpcAuthorizationContext): Boolean = authorize.invoke(context)
    override suspend fun authenticate(
        identity: PeerIdentity, request: OwnedBytes, budget: PayloadBudget,
    ): RpcAuthorizationScope? {
        val allowance = budget.tryReserve(4L * request.size + 32_768)
            ?: throw RpcFailure(
                RpcFailureKind.Overloaded, RpcFailurePhase.Admission,
            )
        return try {
            val decoded = RpcBodyCodec.decode(
                procedure.request, request, requestLimit, budget, allowance, releaseReservation = false,
            )
            authenticate.invoke(identity, decoded)
        } finally { allowance.release() }
    }
}
