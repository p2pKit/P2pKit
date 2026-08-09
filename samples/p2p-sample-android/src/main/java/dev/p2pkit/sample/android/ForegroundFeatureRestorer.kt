package dev.p2pkit.sample.android

import dev.p2pkit.core.FeatureState
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first

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
