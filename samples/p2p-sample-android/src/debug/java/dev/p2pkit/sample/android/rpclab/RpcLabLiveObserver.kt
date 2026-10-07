package dev.p2pkit.sample.android.rpclab

import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.sample.rpc.RpcMetricCard
import dev.p2pkit.sample.rpc.RpcNearbyHost
import dev.p2pkit.sample.rpc.RpcKnownDevice
import dev.p2pkit.sample.rpc.RpcDiscoveryConnectionStatus
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/** Local UI identity only: never pass a pending row or its string representation to diagnostics. */
internal data class RpcLabPendingRequest(
    val requestId: String, val fingerprint: String, val origin: String = "Invitation",
)

internal data class RpcLabLiveSnapshot(
    val asHost: Boolean,
    val state: String,
    val clients: Int,
    val completed: Long,
    val queued: Int,
    val pending: List<RpcLabPendingRequest>?,
    val historyRevision: Long = 0,
    val nearby: List<RpcNearbyHost> = emptyList(),
    val trusted: List<RpcKnownDevice> = emptyList(),
    val connection: RpcDiscoveryConnectionStatus? = null,
    val networkActivity: String = "Idle",
    val metrics: List<RpcMetricCard> = emptyList(),
) {
    val safeState: String get() = RpcLabFeedback.safeState(asHost, state)
}

internal data class RpcLabLiveView(val snapshot: RpcLabLiveSnapshot? = null, val problem: String? = null)

/**
 * Main-thread owner of one foreground-only sampler of already-cached values. No network or role actions.
 * A session identity fences even a synchronous reader that retires/replaces its own observation.
 */
internal class RpcLabLiveObserver(
    private val scope: CoroutineScope,
    private val changed: (RpcLabLiveSnapshot) -> Unit,
    private val failed: (Exception) -> Unit,
) {
    private class Session(val owner: Any, val read: () -> RpcLabLiveSnapshot) { var job: Job? = null }
    private var session: Session? = null
    private val mutableView = MutableStateFlow(RpcLabLiveView())
    val view = mutableView.asStateFlow()

    fun start(owner: Any, read: () -> RpcLabLiveSnapshot) {
        if (session?.owner === owner) return
        stop()
        val current = Session(owner, read)
        session = current
        val job = scope.launch(start = CoroutineStart.LAZY) {
            try {
                while (isActive && session === current) {
                    sample(current)
                    delay(INTERVAL_MILLIS)
                }
            } finally {
                if (session === current) {
                    session = null
                    mutableView.value = RpcLabLiveView()
                }
            }
        }
        current.job = job
        job.start()
    }

    /** Optional explicit local reread; it neither creates a timer nor changes its schedule. */
    fun refresh(): RpcLabLiveSnapshot? {
        val current = session ?: return null
        sample(current)
        return if (session === current) mutableView.value.snapshot else null
    }

    fun stop() {
        val retired = session
        session = null
        retired?.job?.cancel()
        mutableView.value = RpcLabLiveView()
    }

    private fun sample(current: Session) {
        if (session !== current) return
        val sample = try {
            // Copy the row list to avoid retaining a mutable list supplied by an adapter.
            current.read().let { it.copy(pending = it.pending?.toList()) }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            if (session !== current) return
            val safe = if (error is RpcFailure) "${error.kind.name}/${error.phase.name}/${error.executionEvidence.name}"
                else "LocalOrProtocolFailure"
            val next = RpcLabLiveView(problem = safe)
            if (mutableView.value != next) {
                mutableView.value = next // A failed read must not leave stale identities available for approval.
                failed(error)
            }
            return
        }
        if (session !== current) return
        val next = RpcLabLiveView(snapshot = sample)
        if (mutableView.value != next) {
            mutableView.value = next
            changed(sample)
        }
    }

    companion object { const val INTERVAL_MILLIS = 500L }
}
