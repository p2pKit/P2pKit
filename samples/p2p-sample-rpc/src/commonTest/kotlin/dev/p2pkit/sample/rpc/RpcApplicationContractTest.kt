package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRetrySafety
import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

class RpcApplicationContractTest {
    private val service = RpcExampleService()

    @Test
    fun sharedWireNamesVersionsAndRetrySafetyAreExplicit() {
        val procedures = listOf(RpcApplicationContract.getUser, RpcApplicationContract.listItems,
            RpcApplicationContract.sendMessage)
        assertEquals(listOf("users.get", "items.list", "message.send"), procedures.map { it.name })
        assertTrue(procedures.all { it.version == 1 })
        assertEquals(RpcRetrySafety.Idempotent, RpcApplicationContract.getUser.retrySafety)
        assertEquals(RpcRetrySafety.Idempotent, RpcApplicationContract.listItems.retrySafety)
        assertEquals(RpcRetrySafety.NeverReinvoke, RpcApplicationContract.sendMessage.retrySafety)
        assertTrue(procedures.all { it.errorLimitBytes == 1_024 && it.responseLimitBytes <= 16_384 })
    }

    @Test
    fun getUserReturnsTypedDataAndSeparatesValidationFromBusinessErrors() {
        assertEquals(UserRecord(123, "Demo user"), assertIs<RpcReply.Success<UserRecord>>(
            service.getUser(UserQuery(123))).value)
        assertEquals(ApplicationProblemCode.UserNotFound, problem(service.getUser(UserQuery(999))).code)
        assertEquals(ApplicationProblemCode.InvalidArgument, problem(service.getUser(UserQuery(0))).code)
        assertEquals(ApplicationProblemCode.InvalidArgument, problem(service.getUser(UserQuery(-1))).code)
    }

    @Test
    fun listItemsPaginatesWithoutUnboundedAllocationOrOffsetOverflow() {
        assertEquals(listOf(ItemRecord(2, "Pen")), assertIs<RpcReply.Success<ItemsPage>>(
            service.listItems(ItemsQuery(1, 1))).value.items)
        assertEquals(3, assertIs<RpcReply.Success<ItemsPage>>(service.listItems(ItemsQuery())).value.total)
        assertTrue(assertIs<RpcReply.Success<ItemsPage>>(
            service.listItems(ItemsQuery(Int.MAX_VALUE, 50))).value.items.isEmpty())
        for (query in listOf(ItemsQuery(-1, 1), ItemsQuery(0, 0), ItemsQuery(0, 51))) {
            assertEquals(ApplicationProblemCode.InvalidArgument, problem(service.listItems(query)).code)
        }
    }

    @Test
    fun messageValidationAndAcknowledgementNeverPromiseExternalDelivery() {
        val receipt = assertIs<RpcReply.Success<MessageReceipt>>(
            service.sendMessage(MessageRequest(123, "hello"), "wire-id")).value
        assertEquals(MessageReceipt("wire-id", 5), receipt)
        for (request in listOf(MessageRequest(0, "hello"), MessageRequest(123, "  "),
            MessageRequest(123, "x".repeat(513)))) {
            assertEquals(ApplicationProblemCode.InvalidArgument, problem(service.sendMessage(request, "id")).code)
        }
        assertEquals(ApplicationProblemCode.RecipientUnavailable,
            problem(service.sendMessage(MessageRequest(999, "private text"), "id")).code)
        assertTrue(!Json.encodeToString(ApplicationProblem.serializer(),
            problem(service.sendMessage(MessageRequest(999, "private text"), "id"))).contains("private text"))
    }

    @Test
    fun schemasRoundTripIncludingUnicodeAndBusinessErrors() {
        val message = MessageRequest(123, "مرحبا 👋")
        assertEquals(message, Json.decodeFromString(MessageRequest.serializer(),
            Json.encodeToString(MessageRequest.serializer(), message)))
        val page = ItemsPage(listOf(ItemRecord(3, "Folder")), 3)
        assertEquals(page, Json.decodeFromString(ItemsPage.serializer(),
            Json.encodeToString(ItemsPage.serializer(), page)))
        val error = ApplicationProblem(ApplicationProblemCode.UserNotFound, "User not found")
        assertEquals(error, Json.decodeFromString(ApplicationProblem.serializer(),
            Json.encodeToString(ApplicationProblem.serializer(), error)))
    }

    private fun problem(reply: RpcReply<*, ApplicationProblem>): ApplicationProblem =
        assertIs<RpcReply.ApplicationError<ApplicationProblem>>(reply).error
}
