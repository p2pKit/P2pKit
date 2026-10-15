package dev.p2pkit.sample.desktop.ui

import java.util.concurrent.CompletableFuture

/** Actual final-exit bridge: a background owner awaits EDT-owned asynchronous cleanup without blocking the EDT. */
internal class DesktopTerminalCleanup(private val dispatch: (() -> Unit) -> Unit) {
    fun retire(stages: List<((Boolean) -> Unit) -> Unit>, drainWorkers: () -> Unit) {
        var clean = true
        var interrupted = Thread.interrupted()
        try {
            for (stage in stages) {
                val result = CompletableFuture<Boolean>()
                // Dispatch failure is uncertain, not permission to run subsequent dependent actions.
                dispatch {
                    val monitor = Any()
                    var returned = false
                    var outcome: Boolean? = null
                    fun deliver(value: Boolean) = synchronized(monitor) {
                        if (outcome == null) outcome = value
                        if (returned) result.complete(checkNotNull(outcome))
                    }
                    try {
                        stage(::deliver)
                    } catch (_: Throwable) {
                        synchronized(monitor) { outcome = false }
                    } finally {
                        synchronized(monitor) {
                            returned = true
                            outcome?.let(result::complete)
                        }
                    }
                }
                while (true) {
                    try {
                        if (!result.get()) clean = false
                        break
                    } catch (_: InterruptedException) {
                        interrupted = true
                    }
                }
            }
            // CompletableFuture may return an already-completed value with interruption still set.
            interrupted = Thread.interrupted() || interrupted
            // Cancellation is not retirement: this callback must join the real parent/child job tree.
            try {
                drainWorkers()
            } catch (failure: InterruptedException) {
                interrupted = true
                throw failure
            }
            interrupted = Thread.interrupted() || interrupted
            check(clean && !interrupted) { "Application cleanup is unproven" }
        } finally {
            if (interrupted) Thread.currentThread().interrupt()
        }
    }
}

/** UI-confined exact-once independent cleanup, including disposal after an attempted terminal close. */
internal class DesktopOnceCleanup(private val action: () -> Unit) {
    private var attempted = false
    private var failure: Throwable? = null
    fun close() {
        if (attempted) {
            failure?.let { throw it }
            return
        }
        attempted = true
        try {
            action()
        } catch (caught: Throwable) {
            failure = caught
            throw caught
        }
    }
}

internal class DesktopTerminalBinding(val conceal: () -> Unit, val retire: () -> Unit)

internal fun usesWindowsTerminalExit(osName: String): Boolean = osName.startsWith("Windows", ignoreCase = true)
