package dev.p2pkit.transport.lan

import java.io.IOException
import java.io.InterruptedIOException
import java.net.SocketTimeoutException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Runs one potentially unbounded blocking handle construction on an isolated
 * daemon thread and gives its caller a real deadline.
 *
 * A timed-out construction retains exclusive ownership until its worker
 * exits. If the factory eventually returns a handle, that orphan is closed
 * before another construction is allowed. A worker that never exits therefore
 * cannot cause an unbounded succession of leaked threads/sockets: later calls
 * fail immediately instead of starting another attempt.
 */
internal class BoundedBlockingHandleCreator<H : Any>(
    private val timeoutMillis: Long,
    private val threadName: String,
    private val closeOrphan: (H) -> Unit,
    private val onCleanupFailure: (Throwable) -> Unit = {},
    private val awaitCompletion: (CountDownLatch, Long) -> Boolean = { completion, timeout ->
        completion.await(timeout, TimeUnit.MILLISECONDS)
    }
) {
    private enum class State {
        Running,
        Succeeded,
        Failed,
        Abandoned,
        Cleaning,
        Poisoned,
        Consumed,
        Cleaned
    }

    private class Attempt<H : Any> {
        val completed = CountDownLatch(1)
        var state: State = State.Running
        var result: H? = null
        var failure: Throwable? = null
        var worker: Thread? = null
    }

    private val gate = Any()
    private var activeAttempt: Attempt<H>? = null

    init {
        require(timeoutMillis > 0) { "timeoutMillis must be positive" }
        require(threadName.isNotBlank()) { "threadName must not be blank" }
    }

    /** Construct one handle or fail after [timeoutMillis] without leaking it. */
    fun create(factory: () -> H): H {
        val attempt = synchronized(gate) {
            activeAttempt?.let { active ->
                throw IOException(
                    "blocking handle creation unavailable: previous attempt is ${active.state}"
                )
            }
            Attempt<H>().also { activeAttempt = it }
        }

        val worker = Thread(
            { runAttempt(attempt, factory) },
            threadName
        ).apply { isDaemon = true }
        attempt.worker = worker
        try {
            worker.start()
        } catch (error: Throwable) {
            synchronized(gate) {
                if (activeAttempt === attempt) activeAttempt = null
                attempt.state = State.Failed
                attempt.failure = error
            }
            throw error
        }

        val completed = try {
            awaitCompletion(attempt.completed, timeoutMillis)
        } catch (interrupted: InterruptedException) {
            abandon(attempt)
            Thread.currentThread().interrupt()
            throw InterruptedIOException("interrupted while creating blocking handle").apply {
                initCause(interrupted)
            }
        }

        if (!completed) {
            synchronized(gate) {
                // The worker can publish immediately after await reports its
                // boundary timeout. Prefer that completed result rather than
                // abandoning an already-created live handle.
                when (attempt.state) {
                    State.Succeeded -> return consumeSuccess(attempt)
                    State.Failed -> throw consumeFailure(attempt)
                    State.Running -> attempt.state = State.Abandoned
                    else -> Unit
                }
            }
            attempt.worker?.interrupt()
            throw SocketTimeoutException(
                "blocking handle creation exceeded ${timeoutMillis}ms"
            )
        }

        return synchronized(gate) {
            when (attempt.state) {
                State.Succeeded -> consumeSuccess(attempt)
                State.Failed -> throw consumeFailure(attempt)
                else -> error("worker completed in unexpected state ${attempt.state}")
            }
        }
    }

    private fun runAttempt(attempt: Attempt<H>, factory: () -> H) {
        val produced = try {
            factory()
        } catch (error: Throwable) {
            synchronized(gate) {
                when (attempt.state) {
                    State.Running -> {
                        attempt.failure = error
                        attempt.state = State.Failed
                    }
                    State.Abandoned -> {
                        attempt.state = State.Cleaned
                        if (activeAttempt === attempt) activeAttempt = null
                    }
                    else -> Unit
                }
            }
            attempt.completed.countDown()
            return
        }

        val orphaned = synchronized(gate) {
            when (attempt.state) {
                State.Running -> {
                    attempt.result = produced
                    attempt.state = State.Succeeded
                    false
                }
                State.Abandoned -> {
                    attempt.state = State.Cleaning
                    true
                }
                else -> true
            }
        }
        attempt.completed.countDown()
        if (!orphaned) return
        cleanOrphan(attempt, produced)
    }

    private fun abandon(attempt: Attempt<H>) {
        var completedOrphan: H? = null
        val constructionWorker = attempt.worker
        synchronized(gate) {
            when (attempt.state) {
                State.Running -> attempt.state = State.Abandoned
                State.Succeeded -> {
                    // The caller can no longer receive this handle. Transfer
                    // it to local orphan cleanup outside the ownership gate.
                    attempt.state = State.Cleaning
                    completedOrphan = attempt.result
                    attempt.result = null
                }
                State.Failed -> {
                    attempt.state = State.Consumed
                    if (activeAttempt === attempt) activeAttempt = null
                }
                else -> Unit
            }
        }
        // If construction won just before the waiting caller was interrupted,
        // closing the completed handle inline would put an unbounded third-
        // party close on the already-cancelled caller. Transfer that sole
        // ownership to one daemon cleanup worker. activeAttempt remains
        // Cleaning, so no parallel construction (or unbounded cleanup-thread
        // succession) is possible until the orphan is closed.
        completedOrphan?.let { orphan -> startCompletedOrphanCleanup(attempt, orphan) }
        constructionWorker?.interrupt()
    }

    private fun startCompletedOrphanCleanup(attempt: Attempt<H>, orphan: H) {
        val cleanupWorker = Thread(
            { cleanOrphan(attempt, orphan) },
            "$threadName-orphan-cleanup"
        ).apply { isDaemon = true }
        try {
            cleanupWorker.start()
        } catch (error: Throwable) {
            synchronized(gate) {
                attempt.failure = error
                attempt.state = State.Poisoned
            }
            runCatching { onCleanupFailure(error) }
        }
    }

    private fun cleanOrphan(attempt: Attempt<H>, orphan: H) {
        try {
            closeOrphan(orphan)
            synchronized(gate) {
                attempt.state = State.Cleaned
                if (activeAttempt === attempt) activeAttempt = null
            }
        } catch (cleanupError: Throwable) {
            synchronized(gate) {
                attempt.failure = cleanupError
                attempt.state = State.Poisoned
            }
            runCatching { onCleanupFailure(cleanupError) }
        }
    }

    private fun consumeSuccess(attempt: Attempt<H>): H {
        val result = checkNotNull(attempt.result) { "successful attempt has no result" }
        attempt.result = null
        attempt.state = State.Consumed
        if (activeAttempt === attempt) activeAttempt = null
        return result
    }

    private fun consumeFailure(attempt: Attempt<H>): Throwable {
        val failure = attempt.failure
            ?: IllegalStateException("failed attempt has no failure")
        attempt.failure = null
        attempt.state = State.Consumed
        if (activeAttempt === attempt) activeAttempt = null
        return failure
    }
}
