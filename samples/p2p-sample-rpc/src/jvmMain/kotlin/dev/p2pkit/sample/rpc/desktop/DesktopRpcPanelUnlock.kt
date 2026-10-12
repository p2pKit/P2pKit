package dev.p2pkit.sample.rpc.desktop

import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Retains the exact result even if EDT dispatch or publication fails; a failed delivery is not an empty profile. */
internal class DesktopRpcPanelUnlockTask(
    scope: CoroutineScope,
    completionDispatcher: CoroutineDispatcher,
    open: () -> DesktopRpcProfileOpenAttempt,
    isClosing: () -> Boolean,
    accept: (DesktopRpcProfileOpenAttempt) -> Unit,
    ready: () -> Unit,
    completionCleanup: () -> Unit,
) {
    @Volatile var attempt: DesktopRpcProfileOpenAttempt? = null
        private set
    @Volatile var completionFailure: Throwable? = null
        private set
    private val completed = CompletableDeferred<Unit>()
    val job: Job = scope.launch(start = CoroutineStart.LAZY) {
        val result = try { open() } catch (failure: Throwable) {
            // Unexpected factory escape has no cleanup receipt; preserve it as unproven ownership.
            DesktopRpcProfileOpenAttempt(Result.failure(failure), failure)
        }
        attempt = result
        withContext(NonCancellable + completionDispatcher) {
            accept(result)
            if (result.result.isSuccess && !isClosing()) ready()
        }
    }

    init {
        job.invokeOnCompletion { cause ->
            var failure = cause
            try { completionCleanup() } catch (cleanup: Throwable) {
                if (failure == null) failure = cleanup else if (failure !== cleanup) failure.addSuppressed(cleanup)
            }
            completionFailure = failure
            completed.complete(Unit)
        }
    }

    /** The panel publishes this task and its job before allowing dispatch or native entry. */
    fun start() { job.start() }
    suspend fun join() { job.join(); completed.await() }
}

/** Creates an unstarted task with its completion cleanup already registered. */
internal fun createDesktopRpcProfileUnlock(
    scope: CoroutineScope,
    completionDispatcher: CoroutineDispatcher,
    open: () -> DesktopRpcProfileOpenAttempt,
    isClosing: () -> Boolean,
    accept: (DesktopRpcProfileOpenAttempt) -> Unit,
    ready: () -> Unit,
    completionCleanup: () -> Unit = {},
): DesktopRpcPanelUnlockTask = DesktopRpcPanelUnlockTask(
    scope, completionDispatcher, open, isClosing, accept, ready, completionCleanup,
)
