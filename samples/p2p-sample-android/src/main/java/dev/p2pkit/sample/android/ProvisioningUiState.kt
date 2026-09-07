package dev.p2pkit.sample.android

import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.WifiCredentials
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.yield

/**
 * Main-thread-confined presentation for one kit at a time; owns collectors, not native resources.
 *
 * Acquisition results are not lifetime guarantees. Subscribe before enabling operations, retain
 * hotspot/join status independently, and reconcile terminal signals before publishing a result.
 * Manager state/networkState are last-owner snapshots, NOT an inventory of both resources:
 * Unknown or a change to the other resource is not evidence that this resource was released.
 */
internal class ProvisioningUiState {
    private val _hotspotResult = MutableStateFlow<LocalNetworkResult?>(null)
    val hotspotResult = _hotspotResult.asStateFlow()
    private val _joinResult = MutableStateFlow<JoinNetworkResult?>(null)
    val joinResult = _joinResult.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy = _busy.asStateFlow()

    private class Run(val manager: NetworkProvisioningManager, parent: CoroutineScope) {
        val scope = CoroutineScope(parent.coroutineContext + SupervisorJob(parent.coroutineContext[Job]))
        var operation: Job? = null
        var hotspot: LocalNetworkResult? = null
        var hotspotFailure: NetworkProvisioningError? = null
        var joined: JoinNetworkResult.Joined? = null
        var joinFailure: NetworkProvisioningError? = null
        var joinDismissed = false
        var joinPending = false
    }

    private var run: Run? = null

    fun attach(manager: NetworkProvisioningManager, scope: CoroutineScope) {
        detach()
        if (!scope.isActive) return
        val owner = Run(manager, scope)
        run = owner
        // UNDISTPATCHED is important for the manager's replay-zero event stream. All callbacks
        // resume on the supplied main-thread scope, and none suspend or launch per-event work.
        owner.scope.launch(start = CoroutineStart.UNDISPATCHED) {
            manager.events.collect { event ->
                if (isCurrent(owner)) onEvent(owner, event)
            }
        }
        owner.scope.launch(start = CoroutineStart.UNDISPATCHED) {
            manager.state.collect { if (isCurrent(owner)) reconcileSnapshots(owner) }
        }
        owner.scope.launch(start = CoroutineStart.UNDISPATCHED) {
            manager.networkState.collect { if (isCurrent(owner)) reconcileSnapshots(owner) }
        }
        owner.scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                awaitCancellation()
            } finally {
                // Parent cancellation need not go through the ViewModel's explicit detach path.
                if (run === owner) detach()
            }
        }
    }

    fun detach() {
        val previous = run
        run = null
        previous?.scope?.cancel()
        previous?.hotspot = null
        previous?.joined = null
        _hotspotResult.value = null
        _joinResult.value = null
        _busy.value = false
    }

    fun startHotspot(onResult: (LocalNetworkResult) -> Unit = {}): Boolean = launchOperation { owner ->
        owner.hotspotFailure = null
        val result = try {
            owner.manager.startLocalNetwork(LocalNetworkConfig())
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: Throwable) {
            LocalNetworkResult.Failed(provisioningError(failure))
        }
        reconcileSnapshots(owner)
        if (!isCurrent(owner)) return@launchOperation
        if (result is LocalNetworkResult.Started || result is LocalNetworkResult.StartedWithoutCredentials) {
            if (hotspotConfirmed(owner)) {
                owner.hotspotFailure = null
                owner.hotspot = result
                _hotspotResult.value = result
            } else {
                failHotspot(owner, owner.hotspotFailure ?: NetworkProvisioningError.HotspotStopped(
                    "Hotspot ended before its start result was delivered. Retry hosting."
                ))
            }
        } else if (owner.hotspot == null) {
            _hotspotResult.value = result
        }
        onResult(_hotspotResult.value ?: result)
    }

    fun stopHotspot(onResult: (Result<Unit>) -> Unit = {}): Boolean = launchOperation { owner ->
        val result = try {
            owner.manager.stopLocalNetwork()
            Result.success(Unit)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: Throwable) {
            Result.failure(failure)
        }
        if (isCurrent(owner)) {
            owner.hotspot = null
            val failure = result.exceptionOrNull()
            if (failure == null) {
                owner.hotspotFailure = null
                _hotspotResult.value = null
            } else {
                failHotspot(owner, provisioningError(failure))
            }
            onResult(result)
        }
    }

    fun joinHotspot(credentials: WifiCredentials, onResult: (JoinNetworkResult) -> Unit = {}): Boolean =
        launchOperation { owner ->
            owner.joinFailure = null
            owner.joinDismissed = false
            owner.joinPending = true
            val result = try {
                owner.manager.joinLocalNetwork(credentials)
            } catch (cancelled: CancellationException) {
                owner.joinPending = false
                throw cancelled
            } catch (failure: Throwable) {
                JoinNetworkResult.Failed(provisioningError(failure))
            }
            reconcileSnapshots(owner)
            if (!isCurrent(owner)) return@launchOperation
            if (result is JoinNetworkResult.Joined) {
                if (joinConfirmed(owner)) {
                    owner.joinFailure = null
                    owner.joined = result
                    owner.joinPending = false
                } else {
                    failJoin(owner, owner.joinFailure ?: NetworkProvisioningError.JoinFailed(
                        "Joined network was released before its result was delivered. Retry joining."
                    ))
                }
            } else if (result !is JoinNetworkResult.Pending) {
                owner.joinPending = false
            }
            // A repeat-join refusal is an operation result, not release of the existing binding.
            _joinResult.value = owner.joined ?: owner.joinFailure?.let(JoinNetworkResult::Failed) ?: result
            onResult(_joinResult.value ?: result)
        }

    /** Hides an established join without releasing it; a pending request may still report its outcome. */
    fun dismissJoin() {
        run?.joinDismissed = run?.joined != null
        _joinResult.value = null
    }

    private fun onEvent(owner: Run, event: NetworkProvisioningEvent) {
        reconcileSnapshots(owner)
        if (!isCurrent(owner)) return
        when (event) {
            is NetworkProvisioningEvent.Failed -> when (val error = event.error) {
                is NetworkProvisioningError.HotspotStopped -> {
                    if (!hotspotConfirmed(owner)) failHotspot(owner, error)
                }
                is NetworkProvisioningError.JoinFailed -> {
                    if (!joinConfirmed(owner)) failJoin(owner, error)
                }
                is NetworkProvisioningError.ManagerClosed -> retireClosedManager(owner)
                // CleanupFailed can concern an already retired resource while the other one is
                // live. Without a resource tag it must not invalidate either successful card.
                else -> Unit
            }
            NetworkProvisioningEvent.LocalNetworkStopped -> {
                if (!hotspotConfirmed(owner)) {
                    owner.hotspot = null
                    owner.hotspotFailure = null
                    _hotspotResult.value = null
                }
            }
            is NetworkProvisioningEvent.NetworkJoined -> {
                // In particular, a queued Joined event cannot undo a newer failure snapshot.
                if (owner.joinPending && owner.joinFailure == null && joinConfirmed(owner)) {
                    owner.joined = JoinNetworkResult.Joined(event.state)
                    owner.joinPending = false
                    _joinResult.value = owner.joined
                }
            }
            is NetworkProvisioningEvent.LocalNetworkStarted,
            is NetworkProvisioningEvent.UserActionRequired -> Unit
        }
    }

    private fun reconcileSnapshots(owner: Run) {
        if (!isCurrent(owner)) return
        // Read current values, not an independently queued collector's possibly older argument.
        when (val state = owner.manager.state.value) {
            NetworkProvisioningState.Closing, NetworkProvisioningState.Closed -> retireClosedManager(owner)
            is NetworkProvisioningState.Failed -> when (val error = state.error) {
                is NetworkProvisioningError.HotspotStopped -> {
                    if (!hotspotConfirmed(owner)) failHotspot(owner, error)
                }
                is NetworkProvisioningError.JoinFailed -> {
                    if (!joinConfirmed(owner)) failJoin(owner, error)
                }
                is NetworkProvisioningError.ManagerClosed -> retireClosedManager(owner)
                else -> Unit
            }
            else -> Unit
        }
    }

    private fun hotspotConfirmed(owner: Run): Boolean =
        owner.manager.state.value == NetworkProvisioningState.LocalNetworkRunning ||
            owner.manager.networkState.value is NetworkState.LocalNetworkHosted

    private fun joinConfirmed(owner: Run): Boolean =
        owner.manager.state.value == NetworkProvisioningState.JoinedNetwork ||
            owner.manager.networkState.value is NetworkState.ConnectedToWifi

    private fun failHotspot(owner: Run, error: NetworkProvisioningError) {
        owner.hotspot = null
        owner.hotspotFailure = error
        _hotspotResult.value = LocalNetworkResult.Failed(error)
    }

    private fun failJoin(owner: Run, error: NetworkProvisioningError) {
        owner.joined = null
        owner.joinFailure = error
        owner.joinPending = false
        owner.joinDismissed = false
        _joinResult.value = JoinNetworkResult.Failed(error)
    }

    private fun retireClosedManager(owner: Run) {
        val hadHotspot = _hotspotResult.value != null
        val hadJoin = _joinResult.value != null || owner.joined != null || owner.joinPending
        detach()
        if (hadHotspot) _hotspotResult.value = LocalNetworkResult.Failed(NetworkProvisioningError.ManagerClosed())
        if (hadJoin) _joinResult.value = JoinNetworkResult.Failed(NetworkProvisioningError.ManagerClosed())
    }

    private fun isCurrent(owner: Run): Boolean = run === owner && owner.scope.isActive

    private fun launchOperation(action: suspend (Run) -> Unit): Boolean {
        val owner = run ?: return false
        if (!isCurrent(owner) || _busy.value || owner.joinPending) return false
        _busy.value = true
        owner.operation = owner.scope.launch {
            try {
                // Let already queued lifecycle notifications settle before a new acquisition
                // can replace the manager's last-owner snapshots. This is not an OS timeout.
                yield()
                reconcileSnapshots(owner)
                if (isCurrent(owner)) action(owner)
            } finally {
                if (isCurrent(owner)) {
                    // Drain emissions made before API completion before offering another operation.
                    yield()
                    if (isCurrent(owner)) _busy.value = false
                }
            }
        }
        return true
    }

    private fun provisioningError(failure: Throwable): NetworkProvisioningError =
        failure as? NetworkProvisioningError ?: NetworkProvisioningError.PlatformError(failure)
}
