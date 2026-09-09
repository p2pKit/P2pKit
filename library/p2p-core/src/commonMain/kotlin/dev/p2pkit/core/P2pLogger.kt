package dev.p2pkit.core

/**
 * Sink for diagnostic messages emitted by the SDK.
 *
 * Apps may supply their own implementation via [dev.p2pkit.core.dsl.P2pKitBuilder.logger]
 * (e.g., bridging to Timber, Logback, or `println`). The default is [NoOp].
 * Logger callbacks are diagnostic-only: an exception thrown by an
 * application logger is isolated and never changes protocol, lifecycle, or
 * cleanup behavior.
 *
 * Calls run synchronously on the emitting SDK execution context, including
 * non-cancellable teardown, and may arrive concurrently on different threads.
 * Implementations must be thread-safe, non-blocking, and return promptly; move
 * slow I/O or log shipping off the callback path. Exception isolation does not
 * bound execution time: a blocking logger can delay SDK operations, including
 * [P2pKit.stop], for as long as it blocks.
 */
public interface P2pLogger {
    public fun debug(message: String)
    public fun info(message: String)
    public fun warn(message: String, throwable: Throwable? = null)
    public fun error(message: String, throwable: Throwable? = null)

    public companion object {
        /** Discards every message. */
        public val NoOp: P2pLogger = object : P2pLogger {
            override fun debug(message: String) {}
            override fun info(message: String) {}
            override fun warn(message: String, throwable: Throwable?) {}
            override fun error(message: String, throwable: Throwable?) {}
        }
    }
}
