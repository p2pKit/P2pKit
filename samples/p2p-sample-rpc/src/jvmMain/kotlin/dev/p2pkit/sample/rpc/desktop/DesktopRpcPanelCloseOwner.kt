package dev.p2pkit.sample.rpc.desktop

import kotlinx.coroutines.CancellationException

/** The containing application may remove the RPC section only after [DesktopRpcCloseResult.Closed]. */
public enum class DesktopRpcCloseResult { Closed, Busy, Failed }

/** EDT-confined, one physical close attempt; no queued navigation and no retry of a failed vault close. */
internal class DesktopRpcPanelCloseOwner {
    private enum class State { Open, Closing, Closed, Failed }
    private var state = State.Open
    private var terminalRequested = false
    private var terminalSubscriber: ((DesktopRpcCloseResult) -> Unit)? = null

    fun request(
        unlocking: Boolean,
        completed: (DesktopRpcCloseResult) -> Unit,
        begin: ((DesktopRpcCloseResult) -> Unit) -> Unit,
    ) {
        when {
            state == State.Closed -> completed(DesktopRpcCloseResult.Closed)
            state == State.Failed -> completed(DesktopRpcCloseResult.Failed)
            unlocking || state == State.Closing || terminalRequested -> completed(DesktopRpcCloseResult.Busy)
            else -> beginClose(completed, begin)
        }
    }

    /** One bounded terminal waiter subscribes to an existing attempt; unlocking must be joined by [begin]. */
    fun requestTerminal(
        completed: (DesktopRpcCloseResult) -> Unit,
        begin: ((DesktopRpcCloseResult) -> Unit) -> Unit,
    ) {
        when {
            state == State.Closed -> completed(DesktopRpcCloseResult.Closed)
            state == State.Failed -> completed(DesktopRpcCloseResult.Failed)
            terminalRequested -> completed(DesktopRpcCloseResult.Busy)
            else -> {
                terminalRequested = true
                terminalSubscriber = completed
                if (state == State.Open) beginClose(null, begin)
            }
        }
    }

    private fun beginClose(
        completed: ((DesktopRpcCloseResult) -> Unit)?,
        begin: ((DesktopRpcCloseResult) -> Unit) -> Unit,
    ) {
        fun finish(result: DesktopRpcCloseResult) {
            if (state != State.Closing) return
            check(result != DesktopRpcCloseResult.Busy) { "Physical close must have a terminal result" }
            state = if (result == DesktopRpcCloseResult.Closed) State.Closed else State.Failed
            val terminal = terminalSubscriber.also { terminalSubscriber = null }
            try { completed?.invoke(result) } finally { terminal?.invoke(result) }
        }
        state = State.Closing
        try { begin(::finish) } catch (failure: Exception) {
            // Retain ownership even if close could not be scheduled. Never retry a partial physical close.
            if (state != State.Closing) throw failure
            finish(DesktopRpcCloseResult.Failed)
        }
    }
}

/** Actual worker return precedes construction; notification also waits for both scopes and cancel() to return. */
internal class DesktopRpcPanelDrainCompletion(
    initialFailure: Throwable?,
    private val expectedCancellation: CancellationException,
    private val completed: (Throwable?) -> Unit,
) {
    private val monitor = Any()
    private var failure = initialFailure
    private var delivered = 0

    fun scopeCompleted(cause: Throwable?) = observe(1, cause?.takeUnless { it === expectedCancellation })
    fun ownersCompleted(cause: Throwable?) = observe(2, cause)
    fun cancellationReturned(cause: Throwable?) = observe(4, cause)

    private fun observe(part: Int, cause: Throwable?) {
        val notify = synchronized(monitor) {
            if (delivered and part != 0) return
            if (cause != null) {
                val primary = failure
                if (primary == null) failure = cause
                else if (primary !== cause) primary.addSuppressed(cause)
            }
            delivered = delivered or part
            delivered == 7
        }
        if (notify) completed(synchronized(monitor) { failure })
    }
}
