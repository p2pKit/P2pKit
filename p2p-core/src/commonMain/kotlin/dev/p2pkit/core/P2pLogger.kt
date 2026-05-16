package dev.p2pkit.core

/**
 * Sink for diagnostic messages emitted by the SDK.
 *
 * Apps may supply their own implementation via [dev.p2pkit.core.dsl.P2pKitBuilder.logger]
 * (e.g., bridging to Timber, Logback, or `println`). The default is [NoOp].
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
