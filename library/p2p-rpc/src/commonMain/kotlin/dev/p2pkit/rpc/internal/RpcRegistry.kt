package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PayloadLease
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.rpc.RpcCallContext
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
    suspend fun authorize(identity: PeerIdentity): Boolean
    suspend fun execute(
        context: RpcCallContext,
        request: OwnedBytes,
        budget: PayloadBudget,
        decodeAllowance: PayloadLease,
        resultAllowance: PayloadLease,
        beforeHandler: () -> Unit,
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
        beforeHandler: () -> Unit,
    ): EncodedReply {
        val decoded = RpcBodyCodec.decode(procedure.request, request, requestLimit, budget, decodeAllowance)
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
