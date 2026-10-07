package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.rpc.RpcRequestTotals
import kotlin.test.Test
import kotlin.test.assertEquals

class RpcRequestMetricsTest {
    @Test
    fun allFrontendsShareTheSameOutcomeLabelsAndNeverCallCompletedSuccessful() {
        val metrics = rpcRequestMetrics(RpcRequestTotals(20, 4, 3, 2, 1, 5, 7),
            RpcDiagnostics(completedCalls = 15, runningCalls = 3, queuedCalls = 2), 6)
        assertEquals(listOf("accepted", "active", "queued", "success", "business", "failed", "cancelled", "timeout",
            "refused", "omitted"), metrics.map { it.id })
        assertEquals(listOf(20L, 3L, 2L, 4L, 3L, 2L, 1L, 5L, 7L, 6L), metrics.map { it.value })
        assertEquals("Refused attempts", metrics.single { it.id == "refused" }.label)
    }
}
