package dev.p2pkit.core.internal

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/**
 * One elapsed budget for session-controlled waits, not a preemptive deadline
 * for lock admission, scheduling or inline host callbacks. The clock and the
 * deadline dispatcher must share a time domain; keep-alive's test clock is
 * deliberately independent. No absolute deadline addition can overflow.
 */
internal class SessionCleanupBudget(
    private val timeoutMillis: Long,
    private val clock: () -> Long,
    private val deadlineDispatcher: CoroutineDispatcher
) {
    private val startedAt = clock()

    init {
        require(timeoutMillis > 0L) { "timeoutMillis must be positive" }
    }

    suspend fun <T> await(
        completion: Deferred<T>,
        phaseLimitMillis: Long
    ): BoundedOperationResult<T> = waitFor(phaseLimitMillis, { completion.isCompleted }) {
        completion.await()
    }

    suspend fun join(job: Job, phaseLimitMillis: Long): BoundedOperationResult<Unit> =
        waitFor(phaseLimitMillis, { job.isCompleted }) { job.join() }

    suspend fun <T> awaitResult(
        completion: Deferred<BoundedOperationResult<T>>,
        phaseLimitMillis: Long
    ): BoundedOperationResult<T> = when (val observed = await(completion, phaseLimitMillis)) {
        is BoundedOperationResult.Success -> observed.value
        is BoundedOperationResult.Failure -> observed
        is BoundedOperationResult.TimedOut -> observed
    }

    /** Only await completion signals here; never execute a resource callback inline. */
    suspend fun <T> waitFor(
        phaseLimitMillis: Long,
        isComplete: () -> Boolean,
        awaitCompletion: suspend () -> T
    ): BoundedOperationResult<T> {
        require(phaseLimitMillis > 0L) { "phaseLimitMillis must be positive" }
        currentCoroutineContext().ensureActive()
        if (isComplete()) return BoundedOperationResult.Success(awaitCompletion())
        val phaseStartedAt = clock()
        fun remaining(): Long = minOf(
            remainingSince(startedAt, timeoutMillis),
            remainingSince(phaseStartedAt, phaseLimitMillis)
        )
        fun pending(allowance: Long) = BoundedOperationResult.TimedOut(
            allowance,
            OwnedOperationTimeoutException(allowance)
        )
        if (remaining() == 0L) {
            // Already-settled ownership wins even when no wait remains.
            return if (isComplete()) {
                BoundedOperationResult.Success(awaitCompletion())
            } else {
                pending(0L)
            }
        }
        return withContext(deadlineDispatcher) {
            // Dispatch admission consumes the same budget and phase cap.
            // In particular, never manufacture a new 1 ms wait at zero.
            val allowance = remaining()
            if (isComplete()) {
                BoundedOperationResult.Success(awaitCompletion())
            } else {
                val settled = if (allowance == 0L) null else withTimeoutOrNull(allowance) {
                    BoundedOperationResult.Success(awaitCompletion())
                }
                // withTimeoutOrNull consumes only its own timeout. A caller's
                // cancellation is never recategorized as cleanup expiry.
                settled ?: if (isComplete()) {
                    BoundedOperationResult.Success(awaitCompletion())
                } else {
                    pending(allowance)
                }
            }
        }
    }

    private fun remainingSince(start: Long, limit: Long): Long {
        val elapsed = clock() - start
        // Negative means clock regression or an interval beyond Long's
        // representable range. Expire rather than granting a fresh budget.
        return if (elapsed < 0L || elapsed >= limit) 0L else limit - elapsed
    }
}

/**
 * One retained resource attempt. Observation expiry never cancels its worker
 * or abandons a late result. Start is idempotent and does not inherit session
 * runtime cancellation; the supervisor retires only after the worker exits.
 */
internal class RetainedSessionCleanup<T>(
    operationDispatcher: CoroutineDispatcher,
    onFailure: (Throwable) -> Unit,
    operation: suspend () -> T
) {
    val completion = CompletableDeferred<BoundedOperationResult<T>>()
    private val owner = SupervisorJob()
    private val worker = CoroutineScope(owner + operationDispatcher).launch(start = CoroutineStart.LAZY) {
        try {
            val result = try {
                BoundedOperationResult.Success(operation())
            } catch (failure: Throwable) {
                BoundedOperationResult.Failure(failure)
            }
            completion.complete(result)
            if (result is BoundedOperationResult.Failure) {
                // Even a result that arrives after every observer timed out
                // remains diagnostic evidence. A throwing logger must not
                // strand ownership or escape as an unhandled worker failure.
                runCatching { onFailure(result.cause) }
            }
        } finally {
            owner.complete()
        }
    }

    fun start() {
        worker.start()
    }
}

internal fun BoundedOperationResult<*>.sessionCleanupIssue(resource: String): CleanupIssue? = when (this) {
    is BoundedOperationResult.Success -> null
    is BoundedOperationResult.Failure -> CleanupIssue(resource, cause)
    is BoundedOperationResult.TimedOut -> CleanupIssue(
        resource = resource,
        cause = IllegalStateException(
            "cleanup still pending after ${timeoutMillis}ms of remaining wait allowance; work may remain in flight",
            cause
        ),
        deadlineExceeded = true
    )
}
