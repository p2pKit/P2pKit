package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger

/**
 * Returns a logger boundary whose delegate can never alter SDK behavior.
 *
 * [P2pLogger] is a synchronous, host-supplied diagnostic extension point. A
 * delegate may accidentally throw any [Throwable], including a
 * `CancellationException` created by an application logging bridge. Such a
 * failure is not structural cancellation of the SDK coroutine that happened
 * to emit the log, so it must not escape into protocol, ownership, or cleanup
 * paths. The wrapper deliberately does not try to report delegate failures
 * through the same delegate.
 */
internal fun P2pLogger.failureIsolated(): P2pLogger =
    if (this is FailureIsolatingP2pLogger) this else FailureIsolatingP2pLogger(this)

private class FailureIsolatingP2pLogger(
    private val delegate: P2pLogger
) : P2pLogger {
    override fun debug(message: String) = isolate { delegate.debug(message) }

    override fun info(message: String) = isolate { delegate.info(message) }

    override fun warn(message: String, throwable: Throwable?) =
        isolate { delegate.warn(message, throwable) }

    override fun error(message: String, throwable: Throwable?) =
        isolate { delegate.error(message, throwable) }

    private inline fun isolate(block: () -> Unit) {
        try {
            block()
        } catch (_: Throwable) {
            // Diagnostics never own protocol, lifecycle, or resource state.
        }
    }
}
