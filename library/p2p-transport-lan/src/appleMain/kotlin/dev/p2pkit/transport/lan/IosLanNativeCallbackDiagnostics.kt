@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import kotlin.concurrent.Volatile
import platform.Foundation.NSLock

/**
 * Test-opt-in, direct observations of browser leases born within one process-wide epoch.
 * No native objects, peer data or log strings are retained. A lease never changes epochs.
 * The single lock protects only this object's finite state; it never calls transport,
 * coroutine, test or output code. With no installed epoch the capture path returns null.
 */
internal object IosLanNativeCallbackDiagnostics {
    const val MAX_COUNTER = 255

    enum class Availability { AVAILABLE, NOT_INSTALLED, INSTALL_CONFLICT, OBSERVER_FAILURE, CLOSED }

    data class Snapshot(
        val availability: Availability = Availability.NOT_INSTALLED,
        val overflow: Boolean = false,
        val created: Int = 0,
        val started: Int = 0,
        val ready: Int = 0,
        val terminal: Int = 0,
        val raw: Int = 0,
        val current: Int = 0,
        val stale: Int = 0,
        val oldNonNull: Int = 0,
        val newNonNull: Int = 0,
        val batchComplete: Int = 0,
        val batchIncomplete: Int = 0
    ) {
        /** Captured leases only: not a fixture count, peer count, current-state or retirement proof. */
        val witnessesComplete: Boolean
            get() = availability == Availability.AVAILABLE && !overflow && created > 0 &&
                started == created && ready == created && terminal == 0
    }

    class Epoch internal constructor(initialAvailability: Availability) {
        @Volatile internal var open = initialAvailability == Availability.AVAILABLE
        @Volatile internal var observerFailed = false
        internal var unavailable: Availability? = initialAvailability.takeUnless { it == Availability.AVAILABLE }
        internal var overflow = false
        internal var counters = Snapshot()

        fun snapshot(): Snapshot = snapshotEpoch(this)
        fun close() = closeEpoch(this)
    }

    class Lease internal constructor(internal val epoch: Epoch) {
        internal var startObserved = false
        internal var readyObserved = false
        internal var terminalObserved = false

        fun started() = observe(this, Event.STARTED)
        fun ready(currentAtEntry: Boolean) = observe(this, Event.READY, currentAtEntry)
        fun terminal() = observe(this, Event.TERMINAL)
        fun result(currentAtEntry: Boolean, oldNonNull: Boolean, newNonNull: Boolean, batchComplete: Boolean) =
            observe(this, Event.RESULT, currentAtEntry, oldNonNull, newNonNull, batchComplete)

        /** An observation failure invalidates absence claims, never the original callback. */
        fun unavailable() = markUnavailable(epoch)
    }

    private enum class Event { STARTED, READY, TERMINAL, RESULT }
    private val lock = NSLock()
    @Volatile private var active: Epoch? = null

    /** Overlapping tests invalidate both observations; the existing owner is never stolen. */
    fun install(): Epoch = try {
        locked {
            val previous = active
            if (previous != null && previous.open) {
                previous.unavailable = Availability.INSTALL_CONFLICT
                Epoch(Availability.INSTALL_CONFLICT)
            } else {
                Epoch(Availability.AVAILABLE).also { active = it }
            }
        }
    } catch (_: Throwable) {
        active?.observerFailed = true
        Epoch(Availability.OBSERVER_FAILURE)
    }

    /** Called once after native creation, before callback installation/start. */
    fun captureLease(): Lease? {
        if (active == null) return null
        var captured: Epoch? = null
        return try {
            locked {
                val epoch = active ?: return@locked null
                captured = epoch
                if (!epoch.open) return@locked null
                val lease = Lease(epoch)
                epoch.counters = epoch.counters.copy(created = increment(epoch, epoch.counters.created))
                lease
            }
        } catch (_: Throwable) {
            (captured ?: active)?.observerFailed = true
            null
        }
    }

    private fun observe(
        lease: Lease,
        event: Event,
        currentAtEntry: Boolean = false,
        oldNonNull: Boolean = false,
        newNonNull: Boolean = false,
        batchComplete: Boolean = false
    ) {
        val epoch = lease.epoch
        try {
            locked {
                if (!epoch.open) return@locked
                val seen = epoch.counters
                epoch.counters = when (event) {
                    Event.STARTED -> if (lease.startObserved) seen else {
                        lease.startObserved = true
                        seen.copy(started = increment(epoch, seen.started))
                    }
                    Event.READY -> if (!currentAtEntry || lease.readyObserved) seen else {
                        lease.readyObserved = true
                        seen.copy(ready = increment(epoch, seen.ready))
                    }
                    Event.TERMINAL -> if (lease.terminalObserved) seen else {
                        lease.terminalObserved = true
                        seen.copy(terminal = increment(epoch, seen.terminal))
                    }
                    Event.RESULT -> seen.copy(
                        raw = increment(epoch, seen.raw),
                        current = if (currentAtEntry) increment(epoch, seen.current) else seen.current,
                        stale = if (!currentAtEntry) increment(epoch, seen.stale) else seen.stale,
                        oldNonNull = if (oldNonNull) increment(epoch, seen.oldNonNull) else seen.oldNonNull,
                        newNonNull = if (newNonNull) increment(epoch, seen.newNonNull) else seen.newNonNull,
                        batchComplete = if (batchComplete) increment(epoch, seen.batchComplete) else seen.batchComplete,
                        batchIncomplete = if (!batchComplete) {
                            increment(epoch, seen.batchIncomplete)
                        } else seen.batchIncomplete
                    )
                }
            }
        } catch (_: Throwable) {
            epoch.observerFailed = true
        }
    }

    private fun snapshotEpoch(epoch: Epoch): Snapshot = try {
        locked {
            epoch.counters.copy(
                availability = when {
                    epoch.observerFailed -> Availability.OBSERVER_FAILURE
                    epoch.unavailable != null -> epoch.unavailable!!
                    !epoch.open -> Availability.CLOSED
                    active !== epoch -> Availability.NOT_INSTALLED
                    else -> Availability.AVAILABLE
                },
                overflow = epoch.overflow
            )
        }
    } catch (_: Throwable) {
        epoch.observerFailed = true
        Snapshot(availability = Availability.OBSERVER_FAILURE)
    }

    private fun markUnavailable(epoch: Epoch) {
        try {
            locked { if (epoch.open) epoch.observerFailed = true }
        } catch (_: Throwable) {
            if (epoch.open) epoch.observerFailed = true
        }
    }

    private fun closeEpoch(epoch: Epoch) {
        // Even a lock failure must leave old handles unable to mutate a later epoch.
        epoch.open = false
        try {
            locked { if (active === epoch) active = null }
        } catch (_: Throwable) {
            epoch.observerFailed = true
        }
    }

    private fun increment(epoch: Epoch, value: Int): Int = if (value < MAX_COUNTER) value + 1 else {
        epoch.overflow = true
        MAX_COUNTER
    }

    private inline fun <T> locked(block: () -> T): T {
        lock.lock()
        return try { block() } finally { lock.unlock() }
    }
}
