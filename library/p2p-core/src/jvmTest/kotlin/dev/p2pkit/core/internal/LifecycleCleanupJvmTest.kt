package dev.p2pkit.core.internal

import kotlin.test.Test
import kotlin.test.assertIs
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.newSingleThreadContext
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

@OptIn(DelicateCoroutinesApi::class, ExperimentalCoroutinesApi::class)
class LifecycleCleanupJvmTest {

    @Test
    fun lateDisposerDoesNotStarveNestedCleanupOnSameWorkerPool() = runBlocking {
        newSingleThreadContext("late-disposer-regression").use { worker ->
            val entered = CompletableDeferred<Unit>()
            val release = CompletableDeferred<Unit>()
            val nestedResult = CompletableDeferred<BoundedOperationResult<Unit>>()
            val pending = async {
                runBoundedIndependentOperation(
                    timeoutMillis = 50L,
                    operationDispatcher = worker,
                    deadlineDispatcher = Dispatchers.Default,
                    onLateSuccess = {
                        nestedResult.complete(
                            runBoundedIndependentOperation(
                                timeoutMillis = 5_000L,
                                operationDispatcher = worker,
                                deadlineDispatcher = Dispatchers.Default
                            ) { Unit }
                        )
                    }
                ) {
                    entered.complete(Unit)
                    withContext(NonCancellable) { release.await() }
                    Unit
                }
            }

            entered.await()
            assertIs<BoundedOperationResult.TimedOut>(withTimeout(5_000L) { pending.await() })
            release.complete(Unit)
            assertIs<BoundedOperationResult.Success<Unit>>(
                withTimeout(5_000L) { nestedResult.await() }
            )
        }
        Unit
    }
}
