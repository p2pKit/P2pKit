package dev.p2pkit.transport.lan

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.withTimeoutOrNull
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference

/**
 * One-shot in-process control used by the separately staged RPC lab. Only the next owned
 * organization-LAN dial socket can claim it. No read, route, authentication or write limits change.
 */
internal class JvmLanReadPause internal constructor() : AutoCloseable {
    private val attached = AtomicBoolean()
    private val requested = AtomicReference<Window?>()
    private var retired = false
    @Volatile private var constrainedWindow: (() -> Boolean)? = null

    private class Window(val startedNanos: Long) {
        val entered = AtomicBoolean()
        val released = CompletableDeferred<Unit>()
    }

    @Synchronized
    fun pause() {
        check(attached.get() && !retired)
        check(requested.compareAndSet(null, Window(System.nanoTime())))
    }

    fun holdingRead(): Boolean = requested.get()?.let {
        it.entered.get() && !it.released.isCompleted && remaining(it) > 0
    } == true

    @Synchronized
    fun observedConstrainedWindow(): Boolean = !retired && holdingRead() && checkNotNull(constrainedWindow).invoke()

    @Synchronized
    internal fun attach(observe: () -> Boolean) {
        check(!retired && attached.compareAndSet(false, true))
        constrainedWindow = observe
    }

    internal suspend fun beforeSocketRead() {
        val window = requested.get() ?: return
        val remaining = remaining(window)
        if (remaining <= 0 || window.released.isCompleted) return
        window.entered.set(true)
        withTimeoutOrNull(remaining) { window.released.await() }
    }

    @Synchronized
    override fun close() {
        retired = true
        next.compareAndSet(this, null)
        constrainedWindow = null
        requested.get()?.released?.complete(Unit)
    }

    private fun remaining(window: Window): Long = 4_000 - (System.nanoTime() - window.startedNanos) / 1_000_000

    companion object {
        private val next = AtomicReference<JvmLanReadPause?>()

        /** JVM-internal lab bridge. The driver has no access to the actual fd or connection. */
        @JvmStatic
        fun armNext(): JvmLanReadPause = JvmLanReadPause().also {
            check(System.getenv("RPC_CAPACITY_LAB_AUTHORIZED") == "synthetic-private-network-only")
            check(next.compareAndSet(null, it))
        }

        internal fun take(): JvmLanReadPause? = next.getAndSet(null)
    }
}
