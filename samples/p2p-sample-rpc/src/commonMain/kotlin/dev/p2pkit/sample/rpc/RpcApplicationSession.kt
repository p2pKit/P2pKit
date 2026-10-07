package dev.p2pkit.sample.rpc

import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.rpc.RpcCallContext
import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcHostConfiguration
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import kotlinx.coroutines.CancellationException
import kotlinx.serialization.json.Json
import kotlin.time.TimeSource

/** Identical selectable exercises on every frontend, including business and validation failures. */
public enum class RpcApplicationExample { GetUser, ListItems, SendMessage, BusinessError, ValidationError }

/** Shared business examples and UI history; this owner is not a connection, identity store, or diagnostics sink. */
public class RpcApplicationSession {
    public val history: RpcRequestHistory = RpcRequestHistory()
    private val service = RpcExampleService()

    /** The supplied application policy is still rechecked by RPC on admission AND result delivery. */
    public fun register(configuration: RpcHostConfiguration, authorize: suspend (PeerIdentity) -> Boolean) {
        configuration.requestHistoryCapacity = 100
        configuration.register(RpcApplicationContract.getUser, authorize) { context, request ->
            handle(RpcApplicationContract.getUser, context, request) { service.getUser(request) }
        }
        configuration.register(RpcApplicationContract.listItems, authorize) { context, request ->
            handle(RpcApplicationContract.listItems, context, request) { service.listItems(request) }
        }
        configuration.register(RpcApplicationContract.sendMessage, authorize) { context, request ->
            handle(RpcApplicationContract.sendMessage, context, request) {
                service.sendMessage(request, context.requestId.value)
            }
        }
    }

    @Throws(Exception::class)
    public suspend fun getUser(client: RpcClient, userId: Int): RpcReply<UserRecord, ApplicationProblem> =
        invoke(client, RpcApplicationContract.getUser, UserQuery(userId))

    @Throws(Exception::class)
    public suspend fun listItems(client: RpcClient, offset: Int, limit: Int): RpcReply<ItemsPage, ApplicationProblem> =
        invoke(client, RpcApplicationContract.listItems, ItemsQuery(offset, limit))

    @Throws(Exception::class)
    public suspend fun sendMessage(
        client: RpcClient, recipientId: Int, text: String,
    ): RpcReply<MessageReceipt, ApplicationProblem> =
        invoke(client, RpcApplicationContract.sendMessage, MessageRequest(recipientId, text))

    private suspend fun <Q, R> invoke(
        client: RpcClient, procedure: RpcProcedure<Q, R, ApplicationProblem>, request: Q,
    ): RpcReply<R, ApplicationProblem> {
        val started = TimeSource.Monotonic.markNow()
        val local = history.begin(RpcRequestSide.Client, procedure.name, procedure.version, preview(procedure, request))
        try {
            val result = client.callWithDetails(procedure, request)
            complete(local, procedure, result.reply, result.elapsedMillis, result.requestId.value)
            return result.reply
        } catch (cancelled: CancellationException) {
            // Caller cancellation is not evidence that remote side effects were rolled back.
            history.finish(local, RpcRequestOutcome.Cancelled, started.elapsedNow().inWholeMilliseconds,
                errorCode = "CallerCancelled", evidence = RpcExecutionEvidence.MayHaveExecuted)
            throw cancelled
        } catch (failure: RpcFailure) {
            history.finish(local, if (failure.kind == RpcFailureKind.DeadlineExceeded) RpcRequestOutcome.TimedOut
                else RpcRequestOutcome.RpcError, started.elapsedNow().inWholeMilliseconds,
                errorCode = "${failure.kind}.${failure.phase}", requestId = failure.requestId?.value,
                evidence = failure.executionEvidence)
            throw failure
        } catch (failure: Exception) {
            history.finish(local, RpcRequestOutcome.LocalError, started.elapsedNow().inWholeMilliseconds,
                errorCode = "LocalFailure") // No nested exception text or invented execution evidence.
            throw failure
        }
    }

    private fun <Q, R> handle(
        procedure: RpcProcedure<Q, R, ApplicationProblem>, context: RpcCallContext, request: Q,
        action: () -> RpcReply<R, ApplicationProblem>,
    ): RpcReply<R, ApplicationProblem> {
        val local = if (context.hostObservationId == null) {
            history.captureOmitted()
            null // Do not pin a forever-running preview when the engine cannot capture its terminal observation.
        } else history.begin(RpcRequestSide.Host, procedure.name, procedure.version, preview(procedure, request),
            context.requestId.value, context.peer.fingerprint?.value, context.hostIncarnation,
            context.hostObservationId)
        try {
            val reply = action()
            // Final success/failure comes from the engine AFTER encoding and finalization, not this handler return.
            when (reply) {
                is RpcReply.Success -> history.hostResponse(local, Json.encodeToString(procedure.response, reply.value))
                is RpcReply.ApplicationError -> history.hostResponse(local,
                    Json.encodeToString(procedure.applicationError, reply.error), reply.error.code.name)
            }
            return reply
        } catch (failure: Exception) {
            history.hostResponse(local, "[handler failed before response capture]", "HandlerFailed")
            throw failure // Engine records whether execution began, and owns the terminal state.
        }
    }

    private fun <Q, R> complete(
        local: Long?, procedure: RpcProcedure<Q, R, ApplicationProblem>, reply: RpcReply<R, ApplicationProblem>,
        elapsed: Long, requestId: String,
    ) {
        when (reply) {
            is RpcReply.Success -> history.finish(local, RpcRequestOutcome.Succeeded, elapsed,
                Json.encodeToString(procedure.response, reply.value), requestId = requestId,
                evidence = RpcExecutionEvidence.HandlerFinished)
            is RpcReply.ApplicationError -> history.finish(local, RpcRequestOutcome.BusinessError, elapsed,
                Json.encodeToString(procedure.applicationError, reply.error), errorCode = reply.error.code.name,
                requestId = requestId, evidence = RpcExecutionEvidence.HandlerFinished)
        }
    }

    private fun <Q, R> preview(procedure: RpcProcedure<Q, R, ApplicationProblem>, request: Q): String {
        // Do not allocate a second enormous encoded string just to show an oversized message rejection.
        if (request is MessageRequest && request.text.length > 1_024) return "[oversized message preview omitted]"
        return Json.encodeToString(procedure.request, request)
    }
}
