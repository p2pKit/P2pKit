package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.rpc.RpcNotification
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.builtins.nullable
import kotlinx.serialization.builtins.serializer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class RpcNotificationsTest {
    @Test
    fun explicitlyNullableNotificationSchemasPreserveNull() = runTest {
        val descriptor = RpcNotification("changed", 1, String.serializer().nullable)
        val budget = PayloadBudget(1_048_576)
        var dropped = 0
        val inbox = RpcNotifications(backgroundScope, mapOf(descriptor.key to descriptor), budget) { dropped++ }
        val observed = mutableListOf<String?>()
        val collector = backgroundScope.launch { inbox.flow(descriptor).collect { observed += it } }
        runCurrent()
        for (value in listOf(null, "value")) {
            val message = WireMessage(
                WireKind.Notify, TEST_REQUEST, TEST_INCARNATION, "changed", 1,
                body = RpcBodyCodec.encode(descriptor.payload, value, descriptor.limitBytes, budget),
            )
            try { inbox.offer(message) } finally { message.release() }
        }
        runCurrent()
        assertEquals(listOf(null, "value"), observed)
        assertEquals(0, dropped)
        inbox.close()
        collector.cancel()
        runCurrent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun notificationsAreBoundedNonReplayedAndDoNotHoldPayloadsAfterClose() = runTest {
        val descriptor = RpcNotification("changed", 1, String.serializer())
        val budget = PayloadBudget(2L * 1_048_576)
        var dropped = 0
        val inbox = RpcNotifications(backgroundScope, mapOf(descriptor.key to descriptor), budget) { dropped++ }
        fun offer(value: String) {
            val message = WireMessage(
                WireKind.Notify, TEST_REQUEST, TEST_INCARNATION, "changed", 1,
                body = RpcBodyCodec.encode(String.serializer(), value, 16_384, budget),
            )
            try { inbox.offer(message) } finally { message.release() }
        }
        offer("before subscription")
        runCurrent()
        val gate = CompletableDeferred<Unit>()
        val observed = mutableListOf<String>()
        val collector = backgroundScope.launch {
            inbox.flow(descriptor).collect { observed += it; gate.await() }
        }
        runCurrent()
        assertTrue(observed.isEmpty())
        repeat(17) { offer("n$it") }
        assertEquals(1, dropped)
        runCurrent()
        assertEquals(listOf("n0"), observed)
        inbox.close()
        runCurrent()
        assertEquals(0L, budget.retainedBytes.value)
        collector.cancel()
        gate.complete(Unit)
    }

    @Test
    fun encodedBytesLimitAppliesBeforeAllSixteenSlotsAreUsed() = runTest {
        val descriptor = RpcNotification("changed", 1, String.serializer())
        val budget = PayloadBudget(2L * 1_048_576)
        var dropped = 0
        val inbox = RpcNotifications(backgroundScope, mapOf(descriptor.key to descriptor), budget) { dropped++ }
        repeat(9) {
            val body = RpcBodyCodec.encode(String.serializer(), "x".repeat(16_382), 16_384, budget)
            val message = WireMessage(WireKind.Notify, TEST_REQUEST, TEST_INCARNATION, "changed", 1, body = body)
            try { inbox.offer(message) } finally { message.release() }
        }
        assertEquals(1, dropped) // Exactly eight 16 KiB bodies fill the 128 KiB inbox.
        inbox.close()
        runCurrent()
        assertEquals(0L, budget.retainedBytes.value)
    }
}
