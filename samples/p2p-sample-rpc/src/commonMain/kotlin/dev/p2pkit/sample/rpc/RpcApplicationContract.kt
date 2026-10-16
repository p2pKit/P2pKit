package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRetrySafety
import kotlinx.serialization.Serializable

@Serializable
public data class UserQuery(public val userId: Int)

@Serializable
public data class UserRecord(public val userId: Int, public val name: String)

@Serializable
public data class ItemsQuery(public val offset: Int = 0, public val limit: Int = 20)

@Serializable
public data class ItemRecord(public val itemId: Int, public val title: String)

@Serializable
public data class ItemsPage(public val items: List<ItemRecord>, public val total: Int)

@Serializable
public data class MessageRequest(public val recipientId: Int, public val text: String)

/** An application acknowledgement, not proof of storage or delivery to another person. */
@Serializable
public data class MessageReceipt(public val receiptId: String, public val acceptedCharacters: Int)

@Serializable
public enum class ApplicationProblemCode { InvalidArgument, UserNotFound, RecipientUnavailable }

/** Fixed application messages: no payload, exception text, fingerprint, or endpoint is echoed as an error. */
@Serializable
public data class ApplicationProblem(public val code: ApplicationProblemCode, public val message: String)

/** One wire contract for Android, iOS and JVM. Demo records are synthetic, not contacts or account data. */
public object RpcApplicationContract {
    public val getUser: RpcProcedure<UserQuery, UserRecord, ApplicationProblem> = RpcProcedure(
        "users.get", 1, UserQuery.serializer(), UserRecord.serializer(), ApplicationProblem.serializer(),
        retrySafety = RpcRetrySafety.Idempotent, requestLimitBytes = 1_024, responseLimitBytes = 4_096,
        errorLimitBytes = 1_024,
    )
    public val listItems: RpcProcedure<ItemsQuery, ItemsPage, ApplicationProblem> = RpcProcedure(
        "items.list", 1, ItemsQuery.serializer(), ItemsPage.serializer(), ApplicationProblem.serializer(),
        retrySafety = RpcRetrySafety.Idempotent, requestLimitBytes = 1_024, responseLimitBytes = 16_384,
        errorLimitBytes = 1_024,
    )
    // A message may have side effects. A lost reply must not cause automatic reinvocation.
    public val sendMessage: RpcProcedure<MessageRequest, MessageReceipt, ApplicationProblem> = RpcProcedure(
        "message.send", 1, MessageRequest.serializer(), MessageReceipt.serializer(), ApplicationProblem.serializer(),
        requestLimitBytes = 4_096, responseLimitBytes = 1_024, errorLimitBytes = 1_024,
    )
}

/** Bounded, stateless example business service. Replace with application-owned transactions in a real product. */
public class RpcExampleService {
    private val users = listOf(UserRecord(123, "Demo user"), UserRecord(456, "Demo operator"))
    private val items = listOf(ItemRecord(1, "Notebook"), ItemRecord(2, "Pen"), ItemRecord(3, "Folder"))

    public fun getUser(request: UserQuery): RpcReply<UserRecord, ApplicationProblem> {
        if (request.userId <= 0) return invalid("userId must be positive")
        return users.firstOrNull { it.userId == request.userId }?.let { RpcReply.Success(it) }
            ?: RpcReply.ApplicationError(ApplicationProblem(ApplicationProblemCode.UserNotFound, "User not found"))
    }

    public fun listItems(request: ItemsQuery): RpcReply<ItemsPage, ApplicationProblem> {
        if (request.offset < 0 || request.limit !in 1..50) return invalid("offset must be nonnegative; limit is 1..50")
        return RpcReply.Success(ItemsPage(items.drop(request.offset).take(request.limit), items.size))
    }

    public fun sendMessage(request: MessageRequest, requestId: String): RpcReply<MessageReceipt, ApplicationProblem> {
        if (request.recipientId <= 0 || request.text.isBlank() || request.text.length > 512) {
            return invalid("recipientId must be positive; text must contain 1..512 characters")
        }
        if (users.none { it.userId == request.recipientId }) return RpcReply.ApplicationError(
            ApplicationProblem(ApplicationProblemCode.RecipientUnavailable, "Recipient unavailable"),
        )
        // Deliberately no inbox, cloud delivery, unbounded log, or durable side-effect claim.
        return RpcReply.Success(MessageReceipt(requestId, request.text.length))
    }

    private fun invalid(message: String): RpcReply.ApplicationError<ApplicationProblem> =
        RpcReply.ApplicationError(ApplicationProblem(ApplicationProblemCode.InvalidArgument, message))
}
