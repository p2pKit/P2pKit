package dev.p2pkit.sample.rpc.desktop

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.launch

/** One foreground role. A new role cannot replace an unfinished or failed physical cleanup. */
internal class DesktopRpcRunOwner<R : Any>(
    private val scope: CoroutineScope,
    private val retire: suspend (R) -> Unit,
) {
    enum class Stage { Idle, Starting, Ready, Working, Stopping, Stopped, Failed }

    data class Snapshot(val stage: Stage, val role: String?, val failure: Throwable?)

    private class Run<R>(val role: String) {
        var resource: R? = null
        var active: Job? = null
        var close: Deferred<Throwable?>? = null
        var ready = false
    }

    private val lock = Any()
    // UI cancellation requests Stop; it must not cancel the physical cleanup itself.
    private val cleanupJob = SupervisorJob()
    private val cleanupScope = CoroutineScope(scope.coroutineContext.minusKey(Job) + cleanupJob)
    private var run: Run<R>? = null
    private var lastClose: Deferred<Throwable?>? = null
    private var view = Snapshot(Stage.Idle, null, null)

    init {
        scope.coroutineContext[Job]?.invokeOnCompletion {
            stop().invokeOnCompletion { cleanupJob.complete() }
        }
    }

    fun snapshot(): Snapshot = synchronized(lock) { view }

    fun current(): R? = synchronized(lock) { run?.takeIf { it.ready && it.close == null }?.resource }

    fun owns(resource: R): Boolean = current() === resource

    fun start(role: String, create: () -> R, initialize: suspend (R) -> Unit): Boolean {
        val job = synchronized(lock) {
            if (run != null || scope.coroutineContext[Job]?.isActive != true) return false
            val selected = Run<R>(role)
            run = selected
            lastClose = null
            view = Snapshot(Stage.Starting, role, null)
            launch(selected, starting = true) {
                val resource = create()
                // No suspension between allocation and publication. Stop joins even a late allocation.
                synchronized(lock) { selected.resource = resource }
                currentCoroutineContext().ensureActive()
                initialize(resource)
                synchronized(lock) { if (selected.close == null) selected.ready = true }
            }
        }
        job.start()
        return true
    }

    fun action(block: suspend (R) -> Unit): Boolean {
        val job = synchronized(lock) {
            val selected = run ?: return false
            if (!selected.ready || selected.active != null || selected.close != null ||
                scope.coroutineContext[Job]?.isActive != true
            ) return false
            val resource = checkNotNull(selected.resource)
            view = Snapshot(Stage.Working, selected.role, null)
            launch(selected, starting = false) { block(resource) }
        }
        job.start()
        return true
    }

    /** Cancelling a call is not rollback. The runtime stays owned until explicit Stop. */
    fun cancelAction() {
        synchronized(lock) { run?.takeIf { it.close == null }?.active }?.cancel()
    }

    fun stop(): Deferred<Throwable?> {
        val result = synchronized(lock) {
            run?.let(::beginClose) ?: lastClose ?: CompletableDeferred<Throwable?>().also {
                it.complete(null)
                lastClose = it
            }
        }
        result.start()
        return result
    }

    private fun launch(selected: Run<R>, starting: Boolean, block: suspend () -> Unit): Job {
        // A completion handler is required: a lazy job cancelled before dispatch never enters finally.
        var failure: Throwable? = null
        val job = scope.launch(start = CoroutineStart.LAZY) {
            try { block() } catch (caught: Throwable) { failure = caught }
        }
        selected.active = job
        job.invokeOnCompletion { cause ->
            val closing = synchronized(lock) {
                if (run !== selected || selected.active !== job) null
                else {
                    selected.active = null
                    val outcome = failure ?: cause
                    if (starting && outcome != null && selected.close == null) {
                        view = Snapshot(Stage.Failed, selected.role, outcome)
                        beginClose(selected)
                    } else {
                        if (selected.close == null) view = Snapshot(Stage.Ready, selected.role, outcome)
                        null
                    }
                }
            }
            closing?.start()
        }
        return job
    }

    // Call under lock. Every caller awaits one physical attempt; never retry a non-idempotent vault.
    private fun beginClose(selected: Run<R>): Deferred<Throwable?> {
        selected.close?.let { return it }
        val predecessor = selected.active
        view = Snapshot(Stage.Stopping, selected.role, view.failure)
        return cleanupScope.async(start = CoroutineStart.LAZY) {
            var failure: Throwable? = null
            try {
                predecessor?.cancelAndJoin()
                val resource = synchronized(lock) { selected.resource }
                if (resource != null) retire(resource)
            } catch (caught: Throwable) {
                failure = caught
            }
            synchronized(lock) {
                check(run === selected)
                if (failure == null) {
                    run = null
                    view = Snapshot(Stage.Stopped, null, view.failure)
                } else {
                    // Keep the exact failed owner's resource/outcome; do not declare it stopped.
                    view = Snapshot(Stage.Failed, selected.role, failure)
                }
            }
            // A value, not an async exception: coroutine stack recovery cannot replace this identity.
            failure
        }.also {
            selected.close = it
            lastClose = it
        }
    }
}

internal fun desktopRpcFailureText(failure: Throwable): String = when (failure) {
    is CancellationException -> "Cancelled; a remote operation may already have executed."
    is dev.p2pkit.rpc.RpcFailure ->
        "RPC ${failure.kind}/${failure.phase}; execution=${failure.executionEvidence}."
    else -> "Operation failed. Check the explicit network, storage and role; private details are not logged."
}
