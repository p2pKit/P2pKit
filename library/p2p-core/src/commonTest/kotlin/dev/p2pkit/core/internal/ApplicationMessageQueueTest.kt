package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.PayloadBudget
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext

class ApplicationMessageQueueTest {
    @Test
    fun matchedReceiveCancelledBeforeLoopBodyReleasesLeaseAndCharge() = runTest {
        val budget = PayloadBudget(1)
        val queue = ApplicationMessageQueue(maxMessages = 1, maxBytes = 513)
        var enteredBody = false
        val receiver = launch(start = CoroutineStart.UNDISPATCHED) {
            for (entry in queue) {
                try {
                    enteredBody = true
                } finally {
                    entry.release()
                }
            }
        }
        try {
            // UNDISPATCHED receive is already waiting. trySend matches it, but the test
            // dispatcher cannot resume the receiver until this coroutine yields.
            assertTrue(queue.trySend(P2pMessage.Binary(byteArrayOf(1)), 513, assertNotNull(budget.tryReserve(1))))
            assertFalse(enteredBody)
            queue.drain()
            assertEquals(1 to 513L, queue.backlog, "the matched entry is no longer in the drainable queue")
            assertEquals(1L, budget.retainedBytes.value)

            queue.close()
            receiver.cancelAndJoin()
            queue.drain()

            assertFalse(enteredBody, "cleanup must not depend on entering the loop body's finally")
            assertEquals(0 to 0L, queue.backlog)
            assertEquals(0L, budget.retainedBytes.value)
            assertNotNull(budget.tryReserve(1)).release()
        } finally {
            withContext(NonCancellable) {
                queue.close()
                receiver.cancelAndJoin()
                queue.drain()
            }
        }
    }

    @Test
    fun ordinaryDeliveryReleasesOnlyItsOwnChargeExactlyOnce() = runTest {
        val budget = PayloadBudget(2)
        val queue = ApplicationMessageQueue(maxMessages = 2, maxBytes = 1_026)
        val first = P2pMessage.Binary(byteArrayOf(1))
        val entered = CompletableDeferred<ApplicationMessageQueue.Entry>()
        val release = CompletableDeferred<Unit>()
        val receiver = launch(start = CoroutineStart.UNDISPATCHED) {
            for (entry in queue) {
                try {
                    entered.complete(entry)
                    release.await()
                } finally {
                    entry.release()
                }
                break
            }
        }
        try {
            assertTrue(queue.trySend(first, 513, assertNotNull(budget.tryReserve(1))))
            val owned = entered.await()
            assertSame(first, owned.message)
            assertTrue(queue.trySend(P2pMessage.Binary(byteArrayOf(2)), 513, assertNotNull(budget.tryReserve(1))))
            assertEquals(2 to 1_026L, queue.backlog)
            assertEquals(2L, budget.retainedBytes.value)

            release.complete(Unit)
            receiver.join()
            assertEquals(1 to 513L, queue.backlog)
            assertEquals(1L, budget.retainedBytes.value)
            owned.release()
            assertEquals(1 to 513L, queue.backlog, "a repeated release must not erase another entry's charge")
            assertEquals(1L, budget.retainedBytes.value)

            queue.close()
            queue.drain()
            queue.drain()
            assertEquals(0 to 0L, queue.backlog)
            assertEquals(0L, budget.retainedBytes.value)
        } finally {
            withContext(NonCancellable) {
                release.complete(Unit)
                receiver.cancelAndJoin()
                queue.close()
                queue.drain()
            }
        }
    }

    @Test
    fun terminalDrainRetainsNonCooperativeReceiverUntilItsLateFinally() = runTest {
        val budget = PayloadBudget(2)
        val queue = ApplicationMessageQueue(maxMessages = 2, maxBytes = 1_026)
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val receiver = launch(start = CoroutineStart.UNDISPATCHED) {
            for (entry in queue) {
                try {
                    withContext(NonCancellable) {
                        entered.complete(Unit)
                        release.await()
                    }
                } finally {
                    entry.release()
                }
                break
            }
        }
        try {
            assertTrue(queue.trySend(P2pMessage.Binary(byteArrayOf(1)), 513, assertNotNull(budget.tryReserve(1))))
            entered.await()
            assertTrue(queue.trySend(P2pMessage.Binary(byteArrayOf(2)), 513, assertNotNull(budget.tryReserve(1))))
            queue.close()
            receiver.cancel()
            queue.drain()
            assertFalse(receiver.isCompleted)
            assertEquals(1 to 513L, queue.backlog)
            assertEquals(1L, budget.retainedBytes.value)

            release.complete(Unit)
            receiver.join()
            queue.drain()
            assertEquals(0 to 0L, queue.backlog)
            assertEquals(0L, budget.retainedBytes.value)
            assertNotNull(budget.tryReserve(2)).release()
        } finally {
            withContext(NonCancellable) {
                release.complete(Unit)
                receiver.cancelAndJoin()
                queue.close()
                queue.drain()
            }
        }
    }

    @Test
    fun failedClosedSendLeavesLeaseWithCallerAndPreservesExistingCharge() = runTest {
        val budget = PayloadBudget(2)
        val queue = ApplicationMessageQueue(maxMessages = 2, maxBytes = 1_026)
        assertTrue(queue.trySend(P2pMessage.Binary(byteArrayOf(1)), 513, assertNotNull(budget.tryReserve(1))))
        queue.close()
        val rejected = assertNotNull(budget.tryReserve(1))
        try {
            assertFalse(queue.trySend(P2pMessage.Binary(byteArrayOf(2)), 513, rejected))
            assertEquals(1 to 513L, queue.backlog)
            assertEquals(2L, budget.retainedBytes.value, "a failed trySend does not acquire the caller's lease")
            rejected.release()
            assertEquals(1L, budget.retainedBytes.value)
            queue.drain()
            assertEquals(0 to 0L, queue.backlog)
            assertEquals(0L, budget.retainedBytes.value)
        } finally {
            rejected.release()
            queue.drain()
        }
    }

    @Test
    fun capacityRejectionDoesNotAcquireLeaseOrChangeBacklog() = runTest {
        val budget = PayloadBudget(2)
        val queue = ApplicationMessageQueue(maxMessages = 1, maxBytes = 513)
        val rejected = assertNotNull(budget.tryReserve(1))
        try {
            assertFalse(queue.trySend(P2pMessage.Binary(byteArrayOf(1)), 514, rejected))
            assertEquals(0 to 0L, queue.backlog)
            assertEquals(1L, budget.retainedBytes.value)
            assertTrue(queue.trySend(P2pMessage.Binary(byteArrayOf(2)), 513, assertNotNull(budget.tryReserve(1))))
            assertFalse(queue.trySend(P2pMessage.Binary(byteArrayOf(1)), 0, rejected))
            assertEquals(1 to 513L, queue.backlog)
            assertEquals(2L, budget.retainedBytes.value)
        } finally {
            rejected.release()
            queue.close()
            queue.drain()
        }
        assertEquals(0 to 0L, queue.backlog)
        assertEquals(0L, budget.retainedBytes.value)
    }
}
