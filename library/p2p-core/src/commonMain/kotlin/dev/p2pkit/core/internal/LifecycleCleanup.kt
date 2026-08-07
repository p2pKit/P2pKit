package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

internal data class CleanupIssue(
    val resource: String,
    val cause: Throwable
)

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
    cleanup: suspend () -> Unit
): CleanupIssue? {
    // The resource method may deliberately enter NonCancellable or block in
    // platform I/O. A structured withTimeout would then wait forever for its
    // child. Give the attempt an independent owner and bound only awaiting its
    // result; cancellation is still requested on timeout, but stop can report
    // and continue even if broken cleanup code ignores that request.
    val cleanupScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val task = cleanupScope.async { cleanup() }
    return try {
        // Keep the deadline on the same independent dispatcher as the task.
        // Besides matching production elapsed time, this prevents a virtual
        // test scheduler from jumping straight to the timeout while the real
        // cleanup worker has not had a chance to run.
        withContext(Dispatchers.Default) {
            withTimeout(timeoutMillis) { task.await() }
        }
        null
    } catch (timeout: TimeoutCancellationException) {
        CleanupIssue(
            resource,
            IllegalStateException("cleanup exceeded ${timeoutMillis}ms", timeout)
        )
    } catch (cancelled: CancellationException) {
        if (preserveCancellation || !currentCoroutineContext().isActive) throw cancelled
        CleanupIssue(resource, cancelled)
    } catch (failure: Throwable) {
        CleanupIssue(resource, failure)
    } finally {
        task.cancel()
        cleanupScope.cancel()
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
