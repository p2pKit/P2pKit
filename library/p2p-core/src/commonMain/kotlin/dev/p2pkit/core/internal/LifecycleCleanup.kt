package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

internal data class CleanupIssue(
    val resource: String,
    val cause: Throwable,
    val deadlineExceeded: Boolean = false
)

internal sealed interface BoundedOperationResult<out T> {
    data class Success<T>(val value: T) : BoundedOperationResult<T>
    data class Failure(val cause: Throwable) : BoundedOperationResult<Nothing>
    data class TimedOut(
        val timeoutMillis: Long,
        val cause: TimeoutCancellationException
    ) : BoundedOperationResult<Nothing>
}

internal class CleanupAggregateException(
    val operation: String,
    val issues: List<CleanupIssue>
) : Exception(
    buildString {
        append(operation)
        append(" failed for ")
        append(issues.size)
        append(" resource(s): ")
        append(issues.joinToString { issue ->
            "${issue.resource} (${issue.cause.message ?: issue.cause::class.simpleName})"
        })
    },
    issues.firstOrNull()?.cause
)

internal suspend fun captureCleanupIssue(
    resource: String,
    timeoutMillis: Long,
    preserveCancellation: Boolean = true,
    operationDispatcher: CoroutineDispatcher = blockingCleanupDispatcher(),
    deadlineDispatcher: CoroutineDispatcher = Dispatchers.Default,
    operationGate: Semaphore? = null,
    cleanup: suspend () -> Unit
): CleanupIssue? = when (
    val result = runBoundedIndependentOperation(
        timeoutMillis = timeoutMillis,
        preserveCancellation = preserveCancellation,
        operationDispatcher = operationDispatcher,
        deadlineDispatcher = deadlineDispatcher,
        operationGate = operationGate,
        operation = cleanup
    )
) {
    is BoundedOperationResult.Success -> null
    is BoundedOperationResult.Failure -> CleanupIssue(resource, result.cause)
    is BoundedOperationResult.TimedOut -> CleanupIssue(
        resource = resource,
        cause = IllegalStateException(
            "cleanup exceeded ${result.timeoutMillis}ms",
            result.cause
        ),
        deadlineExceeded = true
    )
}

/**
 * Run caller-controlled or platform work under an independently owned real
 * deadline.
 *
 * A structured `withTimeout` cannot bound a child that enters
 * [NonCancellable] or blocks in native/application I/O. This helper races the
 * operation's independently owned settlement against a timeout settlement;
 * exactly one wins. If the timeout wins, caller progress is restored even
 * when the worker ignores cancellation. A value produced after that point is
 * handed to [onLateSuccess] so resource-returning operations can close or
 * abort ownership that arrived too late. [onLateSettlement] runs for any
 * operation result that settles after the caller has abandoned it. A
 * producer/result-consumer handshake also covers cancellation after the
 * operation published a value but before the awaiting coroutine resumed.
 * When [operationGate] is supplied, a timed-out worker retains its permit
 * until it really exits; repeated broken callbacks therefore cannot create
 * unbounded detached work.
 */
internal suspend fun <T> runBoundedIndependentOperation(
    timeoutMillis: Long,
    preserveCancellation: Boolean = true,
    operationDispatcher: CoroutineDispatcher = blockingIoDispatcher(),
    deadlineDispatcher: CoroutineDispatcher = Dispatchers.Default,
    operationGate: Semaphore? = null,
    onLateSettlement: suspend (BoundedOperationResult<T>) -> Unit = {},
    onLateSuccess: suspend (T) -> Unit = {},
    operation: suspend () -> T
): BoundedOperationResult<T> {
    require(timeoutMillis > 0L) { "timeoutMillis must be positive" }
    // The resource method may deliberately enter NonCancellable or block in
    // platform I/O. A structured withTimeout would then wait forever for its
    // child. Give the attempt an independent owner and bound only awaiting its
    // result; cancellation is still requested on timeout, but stop can report
    // and continue even if broken cleanup code ignores that request.
    val operationScope = CoroutineScope(SupervisorJob() + operationDispatcher)
    val settlement = CompletableDeferred<BoundedOperationResult<T>>()
    // A producer that publishes first retains responsibility for its result
    // until the awaiting caller explicitly claims or abandons it.
    val deliveryClaimed = CompletableDeferred<Boolean>()
    val task = operationScope.launch {
        var permitAcquired = false
        val result = try {
            operationGate?.acquire()
            permitAcquired = operationGate != null
            BoundedOperationResult.Success(operation())
        } catch (failure: Throwable) {
            BoundedOperationResult.Failure(failure)
        } finally {
            if (permitAcquired) operationGate?.release()
        }
        val producerWonSettlement = settlement.complete(result)
        val claimed = if (producerWonSettlement) {
            withContext(NonCancellable) { deliveryClaimed.await() }
        } else {
            false
        }
        if (!claimed) {
            // Timeout/caller cancellation already abandoned this result. Run
            // ownership callbacks even though this worker was cancelled.
            try {
                // Leave the callback worker before running a disposer. Several
                // late disposers start another bounded operation on that same
                // worker pool; running them inline could occupy every worker
                // while each waits for its queued cleanup, preventing any of
                // those cleanups from ever starting on a fixed-size native
                // dispatcher.
                withContext(NonCancellable + deadlineDispatcher) {
                    onLateSettlement(result)
                    if (result is BoundedOperationResult.Success) {
                        onLateSuccess(result.value)
                    }
                }
            } catch (_: Throwable) {
                // The primary caller has already returned. Late disposal is
                // best effort and must not surface as an unhandled coroutine
                // exception; resource-specific callbacks record their own
                // cleanup diagnostics where available.
            }
        }
    }
    return try {
        // Keep deadline delivery independent from the blocking worker pool. A
        // callback can occupy every worker while ignoring cancellation; its
        // deadline must still fire. Tests use this real dispatcher explicitly
        // rather than allowing a virtual scheduler to jump past a worker that
        // has not had a chance to run.
        var producerResult = false
        val result = try {
            withContext(deadlineDispatcher) {
                withTimeout(timeoutMillis) { settlement.await() }
            }.also { producerResult = true }
        } catch (timeout: TimeoutCancellationException) {
            val timedOut = BoundedOperationResult.TimedOut(timeoutMillis, timeout)
            // Resolve an exact-deadline race in favor of the operation when
            // it already settled. This prevents a successful commit/close
            // from being reported as timed out merely because timeout
            // delivery reached this coroutine first.
            if (settlement.complete(timedOut)) {
                timedOut
            } else {
                settlement.await().also { producerResult = true }
            }
        }
        if (producerResult) {
            // Claim synchronously after one final cancellation check. A
            // cancellation linearized before this point abandons the result;
            // one arriving afterward observes ownership already transferred.
            currentCoroutineContext().ensureActive()
            check(deliveryClaimed.complete(true)) {
                "bounded operation result was already delivered"
            }
        }

        val failure = (result as? BoundedOperationResult.Failure)?.cause
        if (failure is CancellationException &&
            (preserveCancellation || !currentCoroutineContext().isActive)
        ) {
            throw failure
        }
        result
    } catch (cancelled: CancellationException) {
        // Mark the result abandoned before cancelling the worker. A
        // non-cooperative operation that later returns then loses completion
        // and runs onLateSuccess instead of leaking its value.
        deliveryClaimed.complete(false)
        settlement.complete(BoundedOperationResult.Failure(cancelled))
        throw cancelled
    } finally {
        task.cancel()
        operationScope.cancel()
    }
}

internal fun logCleanupIssues(
    logger: P2pLogger,
    operation: String,
    issues: List<CleanupIssue>
) {
    issues.forEach { issue ->
        logger.warn("$operation failed for ${issue.resource}", issue.cause)
    }
}

internal fun cleanupError(
    operation: String,
    issues: List<CleanupIssue>
): P2pError.ConnectionFailed {
    val aggregate = CleanupAggregateException(operation, issues.toList())
    return P2pError.ConnectionFailed(aggregate.message ?: "$operation failed").also {
        it.underlying = aggregate
    }
}
