package dev.p2pkit.transport.lan

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Restart-safe polling owner for the JVM LAN bind target.
 *
 * A generation is published before its first topology read and retired before
 * its job is cancelled. Every observation and rebind request is admitted under
 * the same gate. Consequently a delayed iteration from an old stop/start
 * lifetime cannot overwrite the new observation or enqueue work against the
 * new JmDNS handle.
 */
internal class JvmLanNetworkWatcher(
    private val scope: CoroutineScope,
    private val pollIntervalMillis: Long,
    private val currentTarget: () -> JvmLanBindTarget?,
    private val targetChanged: (
        previous: JvmLanBindTarget?,
        current: JvmLanBindTarget?,
        admit: () -> Boolean
    ) -> Unit
) {
    private class Generation {
        @Volatile
        var active: Boolean = true
    }

    private val gate = Any()
    private var generation: Generation? = null
    private var watcherJob: Job? = null

    @Volatile
    private var observed: JvmLanBindTarget? = null

    fun observedTarget(): JvmLanBindTarget? = observed

    fun isActive(): Boolean = synchronized(gate) {
        generation?.active == true && watcherJob?.isActive == true
    }

    /**
     * Start one polling lifetime and reconcile its initial observation with
     * the target used to construct the already-live JmDNS handle.
     */
    fun start(boundTarget: JvmLanBindTarget?) {
        synchronized(gate) {
            if (generation?.active == true && watcherJob?.isActive == true) return
        }

        val owner = Generation()
        synchronized(gate) {
            // The coordinator serializes starts, but keep this fail-closed if
            // a platform caller ever violates that assumption.
            if (generation?.active == true && watcherJob?.isActive == true) return
            generation = owner
            observed = null
        }

        val initial = try {
            currentTarget()
        } catch (error: Throwable) {
            synchronized(gate) {
                if (generation === owner) {
                    owner.active = false
                    generation = null
                    observed = null
                }
            }
            throw error
        }
        val job = scope.launch(start = CoroutineStart.LAZY) {
            while (isActive) {
                delay(pollIntervalMillis)
                val next = currentTarget()
                synchronized(gate) {
                    if (generation !== owner || !owner.active) return@synchronized
                    val previous = observed
                    if (next != previous) {
                        observed = next
                        targetChanged(previous, next) { owner.active }
                    }
                }
            }
        }

        val installed = synchronized(gate) {
            if (generation !== owner || !owner.active) {
                false
            } else {
                observed = initial
                watcherJob = job
                if (initial != boundTarget) {
                    targetChanged(boundTarget, initial) { owner.active }
                }
                true
            }
        }
        if (installed) job.start() else job.cancel()
    }

    /** Retire publication rights before cancelling the polling coroutine. */
    fun stop() {
        val retiredJob = synchronized(gate) {
            generation?.active = false
            generation = null
            observed = null
            watcherJob.also { watcherJob = null }
        }
        retiredJob?.cancel()
    }
}
