package dev.p2pkit.provisioning.android

/**
 * Retains cleanup work that failed before a native resource could be handed
 * to [AndroidNetworkProvisioningManager]. Entries are keyed by owner identity
 * so repeated cancellation callbacks cannot grow the registry without bound.
 */
internal class RetryableCleanupRegistry {
    private class Entry(
        val owner: Any,
        val cleanup: () -> Unit
    )

    private val lock = Any()
    private val pending = mutableListOf<Entry>()

    fun runOrRetain(owner: Any, cleanup: () -> Unit): Throwable? = synchronized(lock) {
        val failure = runCatching(cleanup).exceptionOrNull()
        pending.removeAll { it.owner === owner }
        if (failure != null) pending += Entry(owner, cleanup)
        failure
    }

    fun retryAll(): List<Throwable> = synchronized(lock) {
        val snapshot = pending.toList().also { pending.clear() }
        val failures = mutableListOf<Throwable>()
        snapshot.forEach { entry ->
            val failure = runCatching(entry.cleanup).exceptionOrNull()
            if (failure != null) {
                failures += failure
                if (pending.none { it.owner === entry.owner }) pending += entry
            }
        }
        failures
    }

    internal fun pendingCount(): Int = synchronized(lock) { pending.size }
}

/**
 * Prevents a second native request while an earlier non-cancellable platform
 * callback is still outstanding. Cancellation of the waiting coroutine does
 * not release this gate; only a real terminal callback can do that.
 */
internal class PendingNativeRequest {
    class Token internal constructor()

    private val lock = Any()
    private var owner: Token? = null

    fun tryBegin(): Token? = synchronized(lock) {
        if (owner != null) null else Token().also { owner = it }
    }

    fun complete(token: Token) = synchronized(lock) {
        if (owner === token) owner = null
    }

    fun isPending(): Boolean = synchronized(lock) { owner != null }
}

/**
 * Retryable cleanup state for one process-wide Wi-Fi network binding.
 *
 * Clearing the process binding and unregistering its callback are independent
 * operations. A failure in either remains pending for a later [close] call.
 * The binding token is deliberately retained until the process binding has
 * actually been cleared, preventing another manager from claiming ownership
 * while sockets may still be routed through the old network.
 */
internal class RetryableJoinCleanup(
    private val clearProcessBinding: () -> Boolean,
    private val unregisterCallback: () -> Unit,
    private val releaseBindingToken: () -> Unit,
    private val report: (String) -> Unit
) {
    private val lock = Any()
    private var terminal = false
    private var bindingInstalled = false
    private var callbackRegistered = true
    private var bindingTokenHeld = true

    /**
     * Installs the first process binding only while this cleanup owner is
     * live. Holding the same lock as [close] prevents a terminal callback
     * from winning and then being followed by a late process-wide bind.
     */
    fun bindInitial(bind: () -> Boolean): Boolean = synchronized(lock) {
        if (terminal || !bindingTokenHeld || bindingInstalled) return@synchronized false
        bind().also { bound ->
            if (bound) bindingInstalled = true
        }
    }

    fun rebind(bind: () -> Boolean): Boolean = synchronized(lock) {
        if (terminal || !bindingTokenHeld) return@synchronized false
        val rebound = runCatching(bind).getOrElse {
            report("process rebind threw: ${it.message ?: it::class.simpleName}")
            false
        }
        if (rebound) bindingInstalled = true
        rebound
    }

    fun close() {
        val failures = synchronized(lock) {
            terminal = true
            buildList {
                if (bindingInstalled) {
                    val clearFailure = runCatching {
                        check(clearProcessBinding()) { "process binding clear rejected" }
                    }.exceptionOrNull()
                    if (clearFailure == null) {
                        bindingInstalled = false
                    } else {
                        report(
                            "process binding clear failed: " +
                                (clearFailure.message ?: clearFailure::class.simpleName)
                        )
                        add(clearFailure)
                    }
                }

                if (!bindingInstalled && bindingTokenHeld) {
                    val releaseFailure = runCatching(releaseBindingToken).exceptionOrNull()
                    if (releaseFailure == null) {
                        bindingTokenHeld = false
                    } else {
                        report(
                            "process binding token release failed: " +
                                (releaseFailure.message ?: releaseFailure::class.simpleName)
                        )
                        add(releaseFailure)
                    }
                }

                if (callbackRegistered) {
                    val unregisterFailure = runCatching(unregisterCallback).exceptionOrNull()
                    if (unregisterFailure == null) {
                        callbackRegistered = false
                    } else {
                        report(
                            "network callback unregister failed: " +
                                (unregisterFailure.message ?: unregisterFailure::class.simpleName)
                        )
                        add(unregisterFailure)
                    }
                }
            }
        }

        if (failures.isNotEmpty()) {
            val first = failures.first()
            failures.drop(1).forEach(first::addSuppressed)
            throw first
        }
    }
}

/**
 * Serializes the currently bound platform network with terminal loss/close.
 * A delayed loss for a superseded network cannot claim the active lease.
 */
internal class CurrentNetworkLease<T : Any>(initial: T) {
    private val lock = Any()
    private var current = initial
    private var terminal = false

    fun snapshot(): T = synchronized(lock) { current }

    fun rebind(
        next: T,
        canRebind: () -> Boolean,
        bind: () -> Boolean
    ): Boolean = synchronized(lock) {
        if (terminal || !canRebind()) return@synchronized false
        bind().also { rebound ->
            if (rebound) current = next
        }
    }

    fun claimLoss(
        lost: T,
        canClaim: () -> Boolean,
        onClaim: () -> Unit
    ): Boolean = synchronized(lock) {
        if (terminal || current != lost || !canClaim()) {
            false
        } else {
            terminal = true
            onClaim()
            true
        }
    }

    fun close(cleanup: () -> Unit) = synchronized(lock) {
        terminal = true
        cleanup()
    }
}
