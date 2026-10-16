package dev.p2pkit.sample.android.rpclab

/** No restart or persistence: this lease belongs to one already-created, idle ordinary RPC role. */
internal class RpcLabAppSwitchWindow(
    private val clock: () -> Long,
    private val schedule: (Long, () -> Unit) -> (() -> Unit),
    private val execution: Execution,
    private val expired: (Any) -> Unit,
) {
    interface Execution {
        fun begin(expired: () -> Unit): Boolean
        fun end()
    }

    private class Lease(val owner: Any, val deadline: Long) {
        var cancel: (() -> Unit)? = null
    }

    private var lease: Lease? = null
    val active: Boolean get() = lease != null

    fun begin(owner: Any): Boolean {
        if (lease != null) return false
        val current = Lease(owner, clock() + LIMIT_MILLIS)
        lease = current
        val cancel = try { schedule(LIMIT_MILLIS) { expire(current) } } catch (_: RuntimeException) {
            release(current)
            return false
        }
        if (lease !== current) { cancel(); return false }
        current.cancel = cancel
        val admitted = try { execution.begin { expire(current) } } catch (_: RuntimeException) { false }
        if (lease === current && clock() >= current.deadline) expire(current)
        if (!admitted || lease !== current) {
            if (lease === current) release(current)
            return false
        }
        return true
    }

    /** Check the original deadline and current network before returning the same owner to the foreground. */
    fun resume(owner: Any?, revalidate: () -> Boolean): Boolean {
        val current = lease ?: return false
        val valid = current.owner === owner && clock() < current.deadline && revalidate()
        if (!valid) { expire(current); return false }
        // Revalidation can synchronously revoke the lease through a network-change callback.
        if (lease !== current) return false
        release(current)
        return true
    }

    fun close() { lease?.let(::release) }

    private fun expire(current: Lease) {
        if (lease !== current) return
        release(current)
        expired(current.owner)
    }

    private fun release(current: Lease) {
        if (lease !== current) return
        lease = null
        current.cancel?.invoke()
        current.cancel = null
        execution.end()
    }

    companion object {
        const val LIMIT_MILLIS = 25_000L

        fun eligible(
            ordinary: Boolean, hasRole: Boolean, creating: Boolean, busy: Boolean,
            operationActive: Boolean, closing: Boolean, cleanupFailed: Boolean,
        ): Boolean = ordinary && hasRole && !creating && !busy && !operationActive && !closing && !cleanupFailed
    }
}
