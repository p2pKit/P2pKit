package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcRetrySafety
import dev.p2pkit.sample.rpc.lab.LabRpcChecks
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class LabRpcChecksTest {
    @Test
    fun realSocketControlsHaveAnExactDistinctInventory() {
        assertEquals(
            listOf("concurrent-correlation", "application-error", "procedure-authorization",
                "sent-deadline", "sent-cancellation", "close-during-call"),
            LabRpcChecks.cases,
        )
        assertEquals(6, LabRpcChecks.cases.toSet().size)
    }

    @Test
    fun labProceduresCannotCollideWithOrExpandCapacityPayloads() {
        val procedures = listOf(
            LabRpcChecks.echo, LabRpcChecks.reject, LabRpcChecks.denied, LabRpcChecks.hold, LabRpcChecks.state,
        )
        assertEquals(5, procedures.map { it.name }.toSet().size)
        assertTrue(procedures.all { it.name.startsWith("lab.checks.") && it.requestLimitBytes == 1024 })
        assertTrue(procedures.all { it.responseLimitBytes == 1024 && it.errorLimitBytes == 256 })
        assertTrue(procedures.all { it.retrySafety == RpcRetrySafety.NeverReinvoke })
        assertFalse(procedures.any {
            it.name in setOf(RpcCapacityContract.echo.name, RpcCapacityContract.largeEcho.name)
        })
    }
}
