package dev.p2pkit.sample.android.rpclab

import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcHostState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

/** In-memory, bounded and opt-in to copy. Never accepts arbitrary event text or exception descriptions. */
internal class RpcLabEventLog {
    enum class Event {
        StartHostRequested, StartClientRequested, HostStarted, ClientCreated, SetupRejected, PermissionRequested,
        InvitationRequested, InvitationReady, InvitationExpired, InvitationCopied, InvitationCopyUnavailable,
        PairRequested, PairConnected, ApprovalRequested, ExactClientApproved, ReconnectRequested, Reconnected,
        EchoRequested, CancelRequested, Cancelled, StopRequested, CleanupCompleted, CleanupFailed,
        NetworkChanged, AppSwitchStarted, AppSwitchReturned, AppSwitchExpired, ScreenLocked,
        CapacityControlFailed, PeerRevoked, DiagnosticCopyFailed,
    }

    private val mutableLines = MutableStateFlow<List<String>>(emptyList())
    val lines = mutableLines.asStateFlow()
    private val mutableLastFailure = MutableStateFlow<String?>(null)
    val lastFailure = mutableLastFailure.asStateFlow()
    private var sequence = 0L

    fun record(event: Event) { append(event.name) }

    fun failure(error: Exception): String {
        val safe = if (error is RpcFailure) "${error.kind.name}/${error.phase.name}/${error.executionEvidence.name}"
            else "LocalOrProtocolFailure"
        mutableLastFailure.value = safe
        append("Failure $safe")
        return safe
    }

    fun snapshot(asHost: Boolean, state: String, clients: Int, completed: Long, queued: Int, pending: Int?): String {
        val safe = RpcLabFeedback.runtime(asHost, state, clients, completed, queued)
        append("Refresh $safe")
        if (asHost && pending != null) append("PendingRequests count=${pending.coerceAtLeast(0)}")
        return safe
    }

    fun echo(completed: Int, expected: Int, elapsedMillis: Long, kind: String?, evidence: String?): String {
        val safeKind = when {
            kind == null -> "Complete"
            kind == "Cancelled" || kind == "LocalOrProtocolFailure" -> kind
            else -> RpcFailureKind.entries.firstOrNull { it.name == kind }?.name ?: "UnknownFailure"
        }
        val safeEvidence = if (evidence == null) "Unavailable"
            else RpcExecutionEvidence.entries.firstOrNull { it.name == evidence }?.name ?: "UnknownEvidence"
        val safe = "Echo replies=${completed.coerceAtLeast(0)}/${expected.coerceAtLeast(0)}; " +
            "elapsedMs=${elapsedMillis.coerceAtLeast(0)}; result=$safeKind; evidence=$safeEvidence; phase=Unavailable"
        if (kind != null) mutableLastFailure.value = safe
        append(safe)
        return safe
    }

    private fun append(safe: String) {
        sequence++
        mutableLines.value = (mutableLines.value + "$sequence $safe").takeLast(CAPACITY)
    }

    companion object { const val CAPACITY = 80 }
}

/** Fixed English test-app wording. State strings cross a native API boundary, so filter before display/export. */
internal object RpcLabFeedback {
    const val PAIR_STARTED = "Pairing started: connecting and negotiating with the selected host. " +
        "Host approval is needed only after the request reaches the host. Keep both apps open."

    fun runtime(asHost: Boolean, state: String, clients: Int, completed: Long, queued: Int): String {
        val allowed = if (asHost) RpcHostState.entries.map { it.name }
            else RpcConnectionState.entries.map { it.name }
        val safeState = state.takeIf { it in allowed } ?: "Unknown"
        val role = if (asHost) "Host" else "Client"
        val peers = if (asHost) "; connected clients=${clients.coerceAtLeast(0)}" else ""
        return "$role state=$safeState$peers; completed=${completed.coerceAtLeast(0)}; " +
            "queued=${queued.coerceAtLeast(0)}"
    }

    fun pending(count: Int?): String = when (count) {
        null -> "Pending requests: not refreshed. After the client taps Pair, tap Refresh status and pairing requests."
        0 -> "Pending requests: 0 at last refresh. Have the other device Start client and Pair, then refresh again."
        else -> "Pending requests: ${count.coerceAtLeast(0)} at last refresh. " +
            "Compare the full client fingerprint on both devices before approving that exact client."
    }
}
