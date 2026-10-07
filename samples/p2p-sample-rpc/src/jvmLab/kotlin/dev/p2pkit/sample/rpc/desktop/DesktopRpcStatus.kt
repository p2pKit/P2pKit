package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcHostState
import dev.p2pkit.sample.rpc.RpcNearbyHost
import dev.p2pkit.sample.rpc.RpcKnownDevice
import dev.p2pkit.sample.rpc.RpcDiscoveryConnectionStatus

internal const val DESKTOP_RPC_STATUS_INTERVAL_MILLIS: Long = 500

internal enum class DesktopRpcRole {
    Host, Client;

    val cardLabels: List<String> get() = if (this == Host) listOf("Clients", "Pending", "Completed", "Queued")
        else listOf("Connected host", "Connection", "Completed", "Queued")
}

/** Local administrator UI only: never log or export request identifiers or fingerprints. */
internal data class DesktopRpcPending(val requestId: String, val fingerprint: String, val origin: String = "Invitation")

internal data class DesktopRpcStatus(
    val role: DesktopRpcRole,
    val state: String,
    val fingerprint: String,
    val clients: Int,
    val completed: Long,
    val queued: Int,
    val pending: List<DesktopRpcPending>,
    val historyRevision: Long = 0,
    val nearby: List<RpcNearbyHost> = emptyList(),
    val trusted: List<RpcKnownDevice> = emptyList(),
    val connection: RpcDiscoveryConnectionStatus? = null,
    val networkActivity: String = "Idle",
) {
    init {
        require(clients >= 0 && completed >= 0 && queued >= 0)
        require(if (role == DesktopRpcRole.Host) RpcHostState.entries.any { it.name == state }
            else RpcConnectionState.entries.any { it.name == state })
        require(role == DesktopRpcRole.Host || (clients == 0 && pending.isEmpty()))
    }

    val counts: List<String> get() = if (role == DesktopRpcRole.Host) {
        listOf(clients.toString(), pending.size.toString(), completed.toString(), queued.toString())
    } else {
        listOf(if (state == RpcConnectionState.Ready.name) "1" else "0", state, completed.toString(), queued.toString())
    }
}

/** Reordering preserves an explicit selection; expiry, replacement and first observation never select a peer. */
internal fun desktopRpcPendingSelection(
    selected: DesktopRpcPending?, pending: List<DesktopRpcPending>,
): Int = if (selected == null) -1 else pending.indexOf(selected)

internal fun desktopRpcCanApprove(
    snapshot: DesktopRpcRunOwner.Snapshot, selected: DesktopRpcPending?,
): Boolean = snapshot.stage == DesktopRpcRunOwner.Stage.Ready && snapshot.role == "Host" &&
    !snapshot.statusUnavailable && snapshot.status?.role == DesktopRpcRole.Host &&
    snapshot.status.state == RpcHostState.Running.name && selected != null && snapshot.status.pending.contains(selected)
