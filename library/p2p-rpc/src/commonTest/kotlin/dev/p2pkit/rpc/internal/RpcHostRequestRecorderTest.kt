package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcHostCallState
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class RpcHostRequestRecorderTest {
    @Test
    fun capturesQueuedRunningAndEachTerminalOutcomeWithExactEvidenceAndNoPayload() {
        val budget = PayloadBudget(1_048_576)
        val recorder = RpcHostRequestRecorder(8, budget, "host-incarnation")
        val cases = listOf(
            Triple(WireKind.Success, 0, RpcHostCallState.Succeeded),
            Triple(WireKind.ApplicationError, 0, RpcHostCallState.BusinessError),
            Triple(WireKind.Failure, WireFailure.HandlerFailed.code, RpcHostCallState.Failed),
            Triple(WireKind.Failure, WireFailure.CancelledBeforeStart.code, RpcHostCallState.Cancelled),
            Triple(WireKind.Failure, WireFailure.DeadlineBeforeStart.code, RpcHostCallState.TimedOut),
        )
        cases.forEachIndexed { index, (kind, code, outcome) ->
            val id = "private-id-$index"
            recorder.accept(id, "private-pin", "users.get", 1, queued = true)
            assertEquals(RpcHostCallState.Queued, recorder.state.value.entries.last().state)
            if (index < 3) recorder.running(id, "private-pin", 10)
            recorder.finish(id, "private-pin", kind, code, 20)
            val row = recorder.state.value.entries.last()
            assertEquals(outcome, row.state)
            assertEquals(20L, row.elapsedMillis)
            assertFalse(row.toString().contains("private" + "-id"))
            assertFalse(row.toString().contains("private" + "-pin"))
            if (index >= 3) assertEquals(RpcExecutionEvidence.RejectedBeforeExecution, row.executionEvidence)
        }
        val exported = recorder.state.value.entries
        @Suppress("UNCHECKED_CAST")
        (exported as MutableList<Any?>).clear()
        assertEquals(5, recorder.state.value.entries.size, "Administrator inspection cannot mutate recorder ownership")
        val totals = recorder.state.value.totals
        assertEquals(5L, totals.accepted)
        assertEquals(listOf(1L, 1L, 1L, 1L, 1L),
            listOf(totals.succeeded, totals.businessErrors, totals.failed, totals.cancelled, totals.timedOut))
        assertEquals(5 * 4096L, recorder.state.value.retainedMetadataBytes)
        assertEquals(recorder.state.value.retainedMetadataBytes, budget.retainedBytes.value)
        recorder.close()
        assertEquals(0L, budget.retainedBytes.value)
        assertTrue(recorder.state.value.entries.isEmpty())
        assertEquals(totals, recorder.state.value.totals)
    }

    @Test
    fun fullActiveHistoryDeclinesCaptureButNeverAccountingAndEvictsOnlyTerminalEntries() {
        val budget = PayloadBudget(8192)
        val recorder = RpcHostRequestRecorder(2, budget, "host")
        recorder.accept("a", "pin", "users.get", 1, false)
        recorder.accept("b", "pin", "users.get", 1, true)
        recorder.accept("c", "pin", "users.get", 1, true)
        assertEquals(listOf("a", "b"), recorder.state.value.entries.map { it.requestId })
        assertEquals(1L, recorder.state.value.droppedCaptures)
        recorder.finish("c", "pin", WireKind.Success, 0, 5)
        assertEquals(1L, recorder.state.value.totals.succeeded)
        recorder.finish("b", "pin", WireKind.Failure, WireFailure.DeadlineBeforeStart.code, 10)
        recorder.accept("d", "pin", "users.get", 1, true)
        assertEquals(listOf("a", "d"), recorder.state.value.entries.map { it.requestId })
        assertEquals(8192L, budget.retainedBytes.value)
        recorder.close(); recorder.close()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun disabledOrBudgetExhaustedHistoryCannotIncreaseRpcLimitsOrHoldUnaccountedMetadata() {
        for (capacity in listOf(0, 100)) {
            val budget = PayloadBudget(4095)
            val recorder = RpcHostRequestRecorder(capacity, budget, "host")
            recorder.accept("a", "pin", "users.get", 1, false)
            assertTrue(recorder.state.value.entries.isEmpty())
            assertEquals(1L, recorder.state.value.totals.accepted)
            assertEquals(if (capacity == 0) 0L else 1L, recorder.state.value.droppedCaptures)
            assertEquals(0L, budget.retainedBytes.value)
            recorder.close()
        }
    }

    @Test
    fun refusedRetryCannotOverwriteAnAdmittedOutcomeOrCountAsAnotherExecution() {
        val recorder = RpcHostRequestRecorder(4, PayloadBudget(16384), "host")
        recorder.accept("same-id", "pin", "users.get", 1, false)
        recorder.finish("same-id", "pin", WireKind.Success, 0, 20)
        recorder.refuse("same-id", "pin", "users.get", 1, WireFailure.AccessRevoked)
        assertEquals(listOf(RpcHostCallState.Succeeded, RpcHostCallState.Refused),
            recorder.state.value.entries.map { it.state })
        assertEquals(1L, recorder.state.value.totals.accepted)
        assertEquals(1L, recorder.state.value.totals.succeeded)
        assertEquals(1L, recorder.state.value.totals.refusedAttempts)
        assertEquals(RpcExecutionEvidence.MayHaveExecuted, recorder.state.value.entries.last().executionEvidence)
        recorder.running("same-id", "pin", 25)
        assertEquals(RpcHostCallState.Succeeded, recorder.state.value.entries.first().state)
        recorder.close()
    }

    @Test
    fun lateCompletionAfterCloseRetainsOnlyTotalsNotIdentityOrBudget() {
        val budget = PayloadBudget(4096)
        val recorder = RpcHostRequestRecorder(1, budget, "host")
        recorder.accept("a", "pin", "users.get", 1, false)
        recorder.close()
        recorder.finish("a", "pin", WireKind.Failure, WireFailure.Cancelled.code, 10)
        assertTrue(recorder.state.value.entries.isEmpty())
        assertEquals(1L, recorder.state.value.totals.cancelled)
        assertEquals(0L, budget.retainedBytes.value)
    }
}
