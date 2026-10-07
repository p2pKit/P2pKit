package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.rpc.RpcRequestTotals

/** Identical bounded dashboard vocabulary on Android, Swift and Swing; no private request data. */
public data class RpcMetricCard(public val id: String, public val label: String, public val value: Long)

internal fun rpcRequestMetrics(
    totals: RpcRequestTotals, diagnostics: RpcDiagnostics, droppedCaptures: Long,
): List<RpcMetricCard> = listOf(
    RpcMetricCard("accepted", "Admitted requests", totals.accepted),
    RpcMetricCard("active", "Active calls", diagnostics.runningCalls.toLong()),
    RpcMetricCard("queued", "Queued calls", diagnostics.queuedCalls.toLong()),
    RpcMetricCard("success", "Succeeded", totals.succeeded),
    RpcMetricCard("business", "Business errors", totals.businessErrors),
    RpcMetricCard("failed", "RPC failures", totals.failed),
    RpcMetricCard("cancelled", "Cancelled", totals.cancelled),
    RpcMetricCard("timeout", "Timed out", totals.timedOut),
    RpcMetricCard("refused", "Refused attempts", totals.refusedAttempts),
    RpcMetricCard("omitted", "Metadata captures omitted", droppedCaptures),
)
