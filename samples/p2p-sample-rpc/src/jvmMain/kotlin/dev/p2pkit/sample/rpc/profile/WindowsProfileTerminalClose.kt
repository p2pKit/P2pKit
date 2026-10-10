package dev.p2pkit.sample.rpc.profile

import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Explicit application-exit boundary; never used for ordinary Stop, Back or profile locking.
 * The native owner is retained until its real return. Expiry means unproven cleanup, not successful cancellation.
 * The completion callback is deadline-bound; returning from it is not proof that the process exited.
 * Not wired to the Windows application: the native provider and installed-runtime qualification remain gated.
 */
internal class WindowsProfileTerminalClose(
    private val conceal: () -> Unit,
    private val retireAllOwners: () -> Unit,
    private val retired: () -> Unit,
    private val arm: (() -> Unit) -> (() -> Unit),
    private val launch: (() -> Unit) -> Unit,
    private val terminate: (Failure) -> Unit,
) {
    enum class Failure { Deadline, Scheduling, Concealment, Ownership, Completion }
    enum class State { Idle, Closing, Completing, Retired, Failed }

    private val monitor = Any()
    private var state = State.Idle
    private var cleanupStarted = false
    private var cancellation: (() -> Unit)? = null
    val snapshot: State get() = synchronized(monitor) { state }

    /** One admission, one cleanup owner, no restart or queue after any terminal outcome. */
    fun requestApplicationExit(): Boolean {
        synchronized(monitor) {
            if (state != State.Idle) return false
            state = State.Closing
        }
        // Arm before touching UI or scheduling cleanup: either callback can fail or stall.
        val cancel = try { arm { fail(Failure.Deadline) } } catch (_: Throwable) {
            fail(Failure.Scheduling)
            return true
        }
        val alreadyFinished = synchronized(monitor) {
            if (state == State.Closing) { cancellation = cancel; false } else true
        }
        if (alreadyFinished) { cancelSafely(cancel); return true }
        try { conceal() } catch (_: Throwable) { fail(Failure.Concealment); return true }
        if (snapshot != State.Closing) return true
        try {
            launch {
                val ownsCleanup = synchronized(monitor) {
                    if (state == State.Closing && !cleanupStarted) { cleanupStarted = true; true } else false
                }
                if (ownsCleanup) {
                    try { retireAllOwners() } catch (_: Throwable) { fail(Failure.Ownership); return@launch }
                    val won = synchronized(monitor) {
                        if (state == State.Closing) { state = State.Completing; true } else false
                    }
                    // A native call returning after expiry cannot turn uncertainty into a successful exit.
                    if (won) {
                        if (snapshot != State.Completing) return@launch
                        try { retired() } catch (_: Throwable) { fail(Failure.Completion); return@launch }
                        val completed = synchronized(monitor) {
                            if (state == State.Completing) { state = State.Retired; true } else false
                        }
                        if (completed) cancelDeadline()
                    }
                }
            }
        } catch (_: Throwable) { fail(Failure.Scheduling) }
        return true
    }

    private fun fail(reason: Failure) {
        val won = synchronized(monitor) {
            if (state == State.Closing || state == State.Completing) {
                state = State.Failed
                true
            } else false
        }
        if (won) {
            // Production termination must not join/interrupt the native owner or wait for shutdown hooks.
            // Do not cancel this deadline before a potentially blocking termination callback.
            terminate(reason)
        }
    }

    private fun cancelDeadline() {
        val cancel = synchronized(monitor) { cancellation.also { cancellation = null } }
        if (cancel != null) cancelSafely(cancel)
    }

    private fun cancelSafely(cancel: () -> Unit) {
        // Timer cancellation is housekeeping, never proof of native cleanup. A stale expiry checks state.
        try { cancel() } catch (_: Throwable) { /* Ownership outcome remains authoritative. */ }
    }

    companion object {
        /**
         * Real JVM scheduling/termination implementation, validation-only until Windows packaging is qualified.
         * Caller must supply the whole application retirement, not just one profile's close operation.
         * No timeout is selected implicitly and no coroutine cancellation is presented as native cancellation.
         */
        fun forValidation(
            deadlineMillis: Long,
            conceal: () -> Unit,
            retireAllOwners: () -> Unit,
            retired: () -> Unit,
        ): WindowsProfileTerminalClose {
            require(deadlineMillis in 1..120_000)
            return WindowsProfileTerminalClose(conceal, retireAllOwners, retired, arm = { expired ->
                val timer = Executors.newSingleThreadScheduledExecutor { action ->
                    Thread(action, "p2pkit-windows-terminal-deadline").apply { isDaemon = false }
                }
                try {
                    val future = timer.schedule({ expired() }, deadlineMillis, TimeUnit.MILLISECONDS)
                    val cancel: () -> Unit = { future.cancel(false); timer.shutdown() }
                    cancel
                } catch (failure: Throwable) {
                    timer.shutdown()
                    throw failure
                }
            }, launch = { close ->
                Thread({ close() }, "p2pkit-windows-terminal-owner").apply { isDaemon = true }.start()
            }, terminate = { Runtime.getRuntime().halt(125) })
        }
    }
}
