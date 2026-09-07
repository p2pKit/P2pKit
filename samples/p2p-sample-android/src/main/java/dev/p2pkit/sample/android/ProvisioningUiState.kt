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
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.yield

/**
 * Main-thread presentation for one kit, attached before its first provisioning call.
 * Owns subscriptions, never native resources. Android's manager snapshots describe
 * the last publishing owner, not both resources: only resource-specific events end
 * a card. In particular, Unknown and another resource's success do not imply loss.
 */
internal class ProvisioningUiState(
    // Use the queued Main dispatcher, NOT Main.immediate: an OS publisher must never
    // resume UI reconciliation/cancellation inline while holding a native manager lock.
    private val renderDispatcher: CoroutineDispatcher = Dispatchers.Main
) {
    private val _hotspotResult = MutableStateFlow<LocalNetworkResult?>(null)
    val hotspotResult = _hotspotResult.asStateFlow()
    // Requested stop without a successful return, not an inventory of native resources.
    private val _hotspotStopPending = MutableStateFlow(false)
    val hotspotStopPending = _hotspotStopPending.asStateFlow()
    private val _joinResult = MutableStateFlow<JoinNetworkResult?>(null)
    val joinResult = _joinResult.asStateFlow()
    private val _busy = MutableStateFlow(false)
    val busy = _busy.asStateFlow()
    private val _joinBusy = MutableStateFlow(false)
    val joinBusy = _joinBusy.asStateFlow()
    private val _joinSuccessCount = MutableStateFlow(0L)
    val joinSuccessCount = _joinSuccessCount.asStateFlow()

    private sealed interface ResourceSignal {
        class Live(val joinedState: NetworkState? = null) : ResourceSignal
        class Ended(val error: NetworkProvisioningError? = null) : ResourceSignal
    }

    private class FailureNotice(val error: NetworkProvisioningError)

    private data class Signals(
        val hotspot: ResourceSignal? = null,
        val join: ResourceSignal? = null,
        val joinSuccesses: Long = 0,
        val failure: FailureNotice? = null,
        val unavailable: NetworkProvisioningError? = null
    )

    private enum class Operation { START, STOP, JOIN }

    private class JoinRequest(val previousFailure: FailureNotice?) {
        var awaitingEvent = false
    }

    private class Run(val manager: NetworkProvisioningManager, parent: CoroutineScope) {
        val scope = CoroutineScope(parent.coroutineContext + SupervisorJob(parent.coroutineContext[Job]))
        // The only cross-thread state. Immutable, atomically reduced snapshots retain BOTH
        // lifetimes even if the main thread is busy and intermediate UI updates conflate.
        val signals = MutableStateFlow(Signals())
        var observed = Signals()
        var operation: Operation? = null
        var hotspot: LocalNetworkResult? = null
        var joined: JoinNetworkResult.Joined? = null
        var joinRequest: JoinRequest? = null
        // A new binding must be visible even if its predecessor's Ended was never rendered.
        var dismissedJoin: ResourceSignal.Live? = null
    }

    private var run: Run? = null

    fun attach(manager: NetworkProvisioningManager, scope: CoroutineScope) {
        detach()
        if (!scope.isActive) return
        val owner = Run(manager, scope)
        run = owner
        owner.scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                awaitCancellation()
            } finally {
                if (run === owner) detach()
            }
        }
        // Register before enabling calls. These two unconfined collectors do ONLY atomic,
        // non-suspending bookkeeping: no UI, callbacks, locks or manager calls. Recording the
        // Android manager's direct hot-flow emissions must not queue behind the main thread
        // or its replay-zero/DROP_OLDEST buffer can lose a resource's terminal notification.
        owner.scope.launch(Dispatchers.Unconfined, start = CoroutineStart.UNDISPATCHED) {
            try {
                manager.events.collect { event -> owner.signals.update { record(it, event) } }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Throwable) {
                observationFailed(owner, failure)
            }
        }
        owner.scope.launch(Dispatchers.Unconfined, start = CoroutineStart.UNDISPATCHED) {
            try {
                manager.state.collect { state ->
                    if (state == NetworkProvisioningState.Closing || state == NetworkProvisioningState.Closed) {
                        owner.signals.update { it.copy(unavailable = NetworkProvisioningError.ManagerClosed()) }
                    }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Throwable) {
                observationFailed(owner, failure)
            }
        }
        owner.scope.launch(renderDispatcher, start = CoroutineStart.UNDISPATCHED) {
            owner.signals.collect { reconcile(owner) }
        }
    }

    fun detach() {
        val previous = run
        run = null
        previous?.scope?.cancel()
        previous?.hotspot = null
        previous?.joined = null
        previous?.joinRequest = null
        previous?.dismissedJoin = null
        _hotspotResult.value = null
        _hotspotStopPending.value = false
        _joinResult.value = null
        _busy.value = false
        _joinBusy.value = false
    }

    fun startHotspot(onResult: (LocalNetworkResult) -> Unit = {}): Boolean =
        !_hotspotStopPending.value && launchOperation(Operation.START) { owner ->
            val result = try {
                owner.manager.startLocalNetwork(LocalNetworkConfig())
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Throwable) {
                LocalNetworkResult.Failed(provisioningError(failure))
            }
            currentCoroutineContext().ensureActive()
            if (result is LocalNetworkResult.Failed) observeClosedResult(owner, result.error)
            reconcile(owner)
            if (!isCurrent(owner)) return@launchOperation
            val reported = when (result) {
                is LocalNetworkResult.Started, is LocalNetworkResult.StartedWithoutCredentials -> {
                    when (val signal = owner.observed.hotspot) {
                        is ResourceSignal.Live -> {
                            owner.hotspot = result
                            _hotspotResult.value = result
                            result
                        }
                        else -> LocalNetworkResult.Failed(
                            (signal as? ResourceSignal.Ended)?.error ?: NetworkProvisioningError.HotspotStopped(
                                "Hotspot lifetime ended or could not be confirmed. Retry hosting."
                            )
                        ).also { _hotspotResult.value = it }
                    }
                }
                else -> result.also { if (owner.hotspot == null) _hotspotResult.value = it }
            }
            onResult(reported)
        }

    fun stopHotspot(onResult: (Result<Unit>) -> Unit = {}): Boolean =
        launchOperation(Operation.STOP) { owner ->
            // Keep the user's stop intent if the API fails or this operation is cancelled.
            // A lifecycle event is not cleanup acknowledgement; only this call can confirm it.
            _hotspotStopPending.value = true
            owner.hotspot = null
            _hotspotResult.value = null
            val result = try {
                owner.manager.stopLocalNetwork()
                Result.success(Unit)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Throwable) {
                Result.failure(failure)
            }
            currentCoroutineContext().ensureActive()
            (result.exceptionOrNull() as? NetworkProvisioningError)?.let { observeClosedResult(owner, it) }
            reconcile(owner)
            if (!isCurrent(owner)) return@launchOperation
            _hotspotStopPending.value = result.isFailure
            _hotspotResult.value = result.exceptionOrNull()?.let { LocalNetworkResult.Failed(provisioningError(it)) }
            onResult(result)
        }

    /**
     * The card's retry action preserves stop intent. [beforeStart] may request permission
     * and return false to defer acquisition; it never runs for busy, retired or stop intent.
     */
    fun retryHotspot(
        onStartResult: (LocalNetworkResult) -> Unit = {},
        onStopResult: (Result<Unit>) -> Unit = {},
        beforeStart: () -> Boolean = { true }
    ): Boolean {
        val owner = run ?: return false
        reconcile(owner)
        if (!isCurrent(owner) || owner.operation != null) return false
        if (_hotspotStopPending.value) return stopHotspot(onStopResult)
        return beforeStart() && startHotspot(onStartResult)
    }

    fun joinHotspot(credentials: WifiCredentials, onResult: (JoinNetworkResult) -> Unit = {}): Boolean =
        launchOperation(Operation.JOIN) { owner ->
            val request = JoinRequest(owner.signals.value.failure)
            owner.joinRequest = request
            val result = try {
                owner.manager.joinLocalNetwork(credentials)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Throwable) {
                JoinNetworkResult.Failed(provisioningError(failure))
            }
            currentCoroutineContext().ensureActive()
            if (result is JoinNetworkResult.Failed) observeClosedResult(owner, result.error)
            request.awaitingEvent = result is JoinNetworkResult.Pending
            reconcile(owner)
            if (!isCurrent(owner)) return@launchOperation
            val reported = when (result) {
                is JoinNetworkResult.Joined -> owner.joined ?: JoinNetworkResult.Failed(
                    (owner.observed.join as? ResourceSignal.Ended)?.error ?: NetworkProvisioningError.JoinFailed(
                        "Joined network was released or could not be confirmed. Retry joining."
                    )
                )
                JoinNetworkResult.Pending -> owner.joined ?: if (owner.joinRequest === request) result else {
                    _joinResult.value ?: result
                }
                else -> result
            }
            if (result !is JoinNetworkResult.Pending || owner.joined != null) owner.joinRequest = null
            // An already-active refusal is not release. Report the actual operation result
            // to the caller, without relabelling the existing binding or undoing dismissal.
            if (owner.joined == null) _joinResult.value = reported
            onResult(reported)
        }

    /** Hide an established join, not its lifetime. Dismissing Pending still allows its final outcome. */
    fun dismissJoin() {
        val owner = run ?: return
        reconcile(owner)
        if (!isCurrent(owner)) return
        owner.dismissedJoin = owner.observed.join as? ResourceSignal.Live
        _joinResult.value = null
    }

    private fun record(previous: Signals, event: NetworkProvisioningEvent): Signals {
        if (previous.unavailable != null) return previous
        return when (event) {
            is NetworkProvisioningEvent.LocalNetworkStarted -> previous.copy(hotspot = ResourceSignal.Live())
            NetworkProvisioningEvent.LocalNetworkStopped -> previous.copy(hotspot = ResourceSignal.Ended())
            is NetworkProvisioningEvent.NetworkJoined -> previous.copy(
                join = ResourceSignal.Live(event.state), joinSuccesses = previous.joinSuccesses + 1
            )
            is NetworkProvisioningEvent.Failed -> when (val error = event.error) {
                is NetworkProvisioningError.HotspotStopped -> previous.copy(hotspot = ResourceSignal.Ended(error))
                is NetworkProvisioningError.JoinFailed -> previous.copy(join = ResourceSignal.Ended(error))
                is NetworkProvisioningError.ManagerClosed -> previous.copy(unavailable = error)
                // CleanupFailed is untagged and can concern an already retired resource.
                // It cannot revoke a live card or overwrite a pending request's terminal signal.
                is NetworkProvisioningError.CleanupFailed -> previous
                else -> previous.copy(failure = FailureNotice(error))
            }
            is NetworkProvisioningEvent.UserActionRequired -> previous
        }
    }

    private fun reconcile(owner: Run) {
        if (!isCurrent(owner)) return
        // Read one current snapshot, never an independently queued, older collector argument.
        val latest = owner.signals.value
        val previous = owner.observed
        owner.observed = latest
        // Success may be followed by release before the UI gets a turn. Credential clearing
        // must still happen even when no Joined card was ever rendered (or it was dismissed).
        _joinSuccessCount.value += latest.joinSuccesses - previous.joinSuccesses
        latest.unavailable?.let { retire(owner, it); return }
        if (latest.hotspot !== previous.hotspot) {
            owner.hotspot = null
            _hotspotResult.value = (latest.hotspot as? ResourceSignal.Ended)?.error?.let(LocalNetworkResult::Failed)
        }
        if (latest.join !== previous.join) {
            when (val signal = latest.join) {
                is ResourceSignal.Live -> {
                    owner.joined = JoinNetworkResult.Joined(requireNotNull(signal.joinedState))
                    owner.joinRequest = null
                    if (owner.dismissedJoin !== signal) {
                        owner.dismissedJoin = null
                        _joinResult.value = owner.joined
                    }
                }
                is ResourceSignal.Ended -> {
                    owner.joined = null
                    owner.joinRequest = null
                    owner.dismissedJoin = null
                    _joinResult.value = signal.error?.let(JoinNetworkResult::Failed)
                }
                null -> Unit
            }
        }
        val request = owner.joinRequest
        val failure = latest.failure
        if (request?.awaitingEvent == true && failure != null && failure !== request.previousFailure) {
            owner.joinRequest = null
            if (owner.joined == null) _joinResult.value = JoinNetworkResult.Failed(failure.error)
        }
        updateBusy(owner)
    }

    private fun observeClosedResult(owner: Run, error: NetworkProvisioningError) {
        if (error is NetworkProvisioningError.ManagerClosed) {
            owner.signals.update { it.copy(unavailable = error) }
        }
    }

    private fun observationFailed(owner: Run, failure: Throwable) {
        val error = NetworkProvisioningError.PlatformError(
            IllegalStateException("Provisioning observation failed (${failure::class.simpleName}); restart the kit.")
        )
        owner.signals.update { if (it.unavailable == null) it.copy(unavailable = error) else it }
    }

    private fun retire(owner: Run, error: NetworkProvisioningError) {
        val hadHotspot = _hotspotResult.value != null || owner.operation == Operation.START ||
            owner.operation == Operation.STOP
        val hadJoin = _joinResult.value != null || owner.joined != null || owner.joinRequest != null ||
            owner.operation == Operation.JOIN
        detach()
        if (hadHotspot) _hotspotResult.value = LocalNetworkResult.Failed(error)
        if (hadJoin) _joinResult.value = JoinNetworkResult.Failed(error)
    }

    private fun isCurrent(owner: Run): Boolean = run === owner && owner.scope.isActive

    private fun launchOperation(kind: Operation, action: suspend (Run) -> Unit): Boolean {
        val owner = run ?: return false
        reconcile(owner)
        if (!isCurrent(owner) || owner.operation != null || (kind == Operation.JOIN && owner.joinRequest != null)) {
            return false
        }
        owner.operation = kind
        updateBusy(owner)
        owner.scope.launch(start = CoroutineStart.UNDISPATCHED) {
            try {
                // Establish finally before the first dispatch/cancellation. This is only a
                // scheduling boundary, NOT a heuristic for draining lifecycle notifications.
                yield()
                if (isCurrent(owner)) action(owner)
            } finally {
                // No suspension: cancellation must not strand busy, nor may a retired run's
                // late result/finalizer change a replacement kit's controls.
                if (run === owner) {
                    owner.operation = null
                    if (kind == Operation.JOIN && owner.joinRequest?.awaitingEvent != true) owner.joinRequest = null
                    reconcile(owner)
                    updateBusy(owner)
                }
            }
        }
        return true
    }

    private fun updateBusy(owner: Run) {
        if (!isCurrent(owner)) return
        _busy.value = owner.operation != null
        _joinBusy.value = _busy.value || owner.joinRequest != null
    }

    private fun provisioningError(failure: Throwable): NetworkProvisioningError =
        failure as? NetworkProvisioningError ?: NetworkProvisioningError.PlatformError(failure)
}
