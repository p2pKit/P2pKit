package dev.p2pkit.core.internal

import kotlin.concurrent.atomics.AtomicInt
import kotlin.concurrent.atomics.ExperimentalAtomicApi
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield

@OptIn(ExperimentalAtomicApi::class, ExperimentalCoroutinesApi::class)
class LifecycleCleanupTest {

    @Test
    fun timeoutRestoresCallerProgressAndDisposesLateValueExactlyOnce() = runBlocking {
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val disposed = AtomicInt(0)
        val pending = async {
            runBoundedIndependentOperation(
                timeoutMillis = 50L,
                operationDispatcher = Dispatchers.Default,
                onLateSuccess = { disposed.addAndFetch(1) }
            ) {
                entered.complete(Unit)
                withContext(NonCancellable) { release.await() }
                "late-value"
            }
        }

        entered.await()
        assertIs<BoundedOperationResult.TimedOut>(withTimeout(5_000) { pending.await() })
        assertEquals(0, disposed.load())

        release.complete(Unit)
        withTimeout(5_000) { while (disposed.load() != 1) yield() }
        assertEquals(1, disposed.load())
    }

    @Test
    fun successfulSettlementReturnsValueWithoutRunningLateDisposer() = runBlocking {
        var disposed = false
        val result = runBoundedIndependentOperation(
            timeoutMillis = 5_000L,
            operationDispatcher = Dispatchers.Default,
            onLateSuccess = { disposed = true }
        ) {
            "owned-value"
        }

        assertEquals("owned-value", assertIs<BoundedOperationResult.Success<String>>(result).value)
        assertFalse(disposed)
    }

    @Test
    fun cancellationAfterProducerSettlementDisposesUnclaimedValueExactlyOnce() = runTest {
        val disposed = AtomicInt(0)
        val caller = backgroundScope.async(start = CoroutineStart.UNDISPATCHED) {
            runBoundedIndependentOperation(
                timeoutMillis = 5_000L,
                operationDispatcher = Dispatchers.Unconfined,
                deadlineDispatcher = StandardTestDispatcher(testScheduler),
                onLateSuccess = { disposed.addAndFetch(1) }
            ) {
                "settled-before-resume"
            }
        }

        // The Unconfined producer has published its value, while the caller
        // is still queued on the deliberately controlled deadline dispatcher.
        caller.cancel()
        runCurrent()
        caller.join()
        runCurrent()

        assertTrue(caller.isCancelled)
        assertEquals(1, disposed.load())
    }

    @Test
    fun cleanupTimeoutIsMachineClassifiableWithoutParsingItsMessage() = runBlocking {
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val pending = async {
            captureCleanupIssue(
                resource = "wedged resource",
                timeoutMillis = 50L,
                operationDispatcher = Dispatchers.Default
            ) {
                entered.complete(Unit)
                withContext(NonCancellable) { release.await() }
            }
        }

        entered.await()
        val issue = withTimeout(5_000) { pending.await() }
        assertEquals("wedged resource", issue?.resource)
        assertTrue(issue?.deadlineExceeded == true)

        release.complete(Unit)
        Unit
    }

    @Test
    fun operationGateBoundsTimedOutWorkersUntilTheyActuallyExit() = runBlocking {
        val gate = Semaphore(1)
        val firstEntered = CompletableDeferred<Unit>()
        val firstRelease = CompletableDeferred<Unit>()
        val firstLateDisposed = CompletableDeferred<Unit>()
        val secondEntries = AtomicInt(0)

        val first = async {
            runBoundedIndependentOperation(
                timeoutMillis = 50L,
                operationDispatcher = Dispatchers.Default,
                operationGate = gate,
                onLateSuccess = { firstLateDisposed.complete(Unit) }
            ) {
                firstEntered.complete(Unit)
                withContext(NonCancellable) { firstRelease.await() }
                "first"
            }
        }
        firstEntered.await()
        assertIs<BoundedOperationResult.TimedOut>(withTimeout(5_000) { first.await() })

        val second = runBoundedIndependentOperation(
            timeoutMillis = 50L,
            operationDispatcher = Dispatchers.Default,
            operationGate = gate
        ) {
            secondEntries.addAndFetch(1)
            "second"
        }
        assertIs<BoundedOperationResult.TimedOut>(second)
        assertEquals(0, secondEntries.load(), "a saturated gate must not start another worker")

        firstRelease.complete(Unit)
        withTimeout(5_000) { firstLateDisposed.await() }

        val third = runBoundedIndependentOperation(
            timeoutMillis = 5_000L,
            operationDispatcher = Dispatchers.Default,
            operationGate = gate
        ) { "third" }
        assertEquals("third", assertIs<BoundedOperationResult.Success<String>>(third).value)
    }
}
