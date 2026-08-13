package dev.p2pkit.sample.android

import dev.p2pkit.core.FeatureState
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first

/**
 * Issues one revocable lease per Activity foreground episode.
 *
 * A later background or foreground signal invalidates all previously issued
 * leases, so an asynchronous restore waiting for the SDK's background stop
 * cannot restart a feature after the app has left the foreground again.
 */
internal class ForegroundRestoreCoordinator {
    internal data class Lease(val generation: Long)

    private val gate = Any()
    private var generation: Long = 0
    private var foreground: Boolean = false

    fun foregrounded(): Lease = synchronized(gate) {
        generation += 1
        foreground = true
        Lease(generation)
    }

    fun backgrounded() = synchronized(gate) {
        generation += 1
        foreground = false
    }

    fun isCurrent(lease: Lease): Boolean = synchronized(gate) {
        foreground && lease.generation == generation
    }
}

/**
 * Orders a host-requested mobile foreground restart after the SDK's
 * asynchronous background pause. Returns true only when [start] ran.
 */
internal suspend fun restoreRequestedFeatureAfterForeground(
    isStillRequested: () -> Boolean,
    states: StateFlow<FeatureState>,
    start: suspend () -> Unit
): Boolean {
    if (!isStillRequested()) return false
    states.first(::isSettledFeatureState)
    if (!isStillRequested()) return false
    start()
    return true
}

internal fun isSettledFeatureState(state: FeatureState): Boolean = when (state) {
    FeatureState.Idle,
    is FeatureState.Failed,
    is FeatureState.PermissionRequired,
    is FeatureState.Unsupported -> true
    FeatureState.Active,
    FeatureState.Starting,
    FeatureState.Stopping -> false
}
