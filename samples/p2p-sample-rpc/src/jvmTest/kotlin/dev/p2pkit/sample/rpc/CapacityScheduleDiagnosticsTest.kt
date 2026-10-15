package dev.p2pkit.sample.rpc

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class CapacityScheduleDiagnosticsTest {
    @Test
    fun allThreeUnsentOutcomesReconcileWithoutBecomingRpcErrorsOrSuccesses() {
        val diagnostics = CapacityScheduleDiagnostics()
        fun record(stage: CapacityDispatchStage) { diagnostics.record(0, stage, 1) }
        repeat(5) { record(CapacityDispatchStage.Considered) }
        record(CapacityDispatchStage.TimerLate)
        record(CapacityDispatchStage.PermitUnavailable)
        repeat(3) {
            record(CapacityDispatchStage.Enqueued)
            record(CapacityDispatchStage.WorkerStarted)
        }
        record(CapacityDispatchStage.WorkerLate)
        repeat(2) { record(CapacityDispatchStage.Dispatched) }
        record(CapacityDispatchStage.Completed)
        record(CapacityDispatchStage.Failed)
        diagnostics.verify(expected = 5, dispatched = 2, completed = 1, failed = 1, missed = 3)
        assertEquals(1L, diagnostics.total(CapacityDispatchStage.TimerLate))
        assertEquals(1L, diagnostics.total(CapacityDispatchStage.PermitUnavailable))
        assertEquals(1L, diagnostics.total(CapacityDispatchStage.WorkerLate))
        assertFailsWith<IllegalStateException> {
            diagnostics.verify(expected = 5, dispatched = 5, completed = 5, failed = 0, missed = 0)
        }
    }

    @Test
    fun diagnosticAccountingRejectsMissingDuplicateAndUnsettledRecords() {
        val diagnostics = CapacityScheduleDiagnostics()
        diagnostics.record(0, CapacityDispatchStage.Considered, 1)
        diagnostics.record(0, CapacityDispatchStage.Enqueued, 1)
        assertFailsWith<IllegalStateException> { diagnostics.verify(1, 0, 0, 0, 0) }
        diagnostics.record(0, CapacityDispatchStage.WorkerStarted, 2)
        diagnostics.record(0, CapacityDispatchStage.WorkerLate, 2)
        diagnostics.verify(1, 0, 0, 0, 1)
        diagnostics.record(0, CapacityDispatchStage.WorkerLate, 2)
        assertFailsWith<IllegalStateException> { diagnostics.verify(1, 0, 0, 0, 1) }
    }

    @Test
    fun observationsAreBoundedToTheUnchangedSchedule() {
        val diagnostics = CapacityScheduleDiagnostics()
        for (tick in listOf(-1, 18_000)) assertFailsWith<IllegalArgumentException> {
            diagnostics.record(tick, CapacityDispatchStage.Considered, 0)
        }
        assertFailsWith<IllegalArgumentException> { diagnostics.record(0, CapacityDispatchStage.Considered, -1) }
        assertFailsWith<IllegalArgumentException> { diagnostics.record(0, CapacityDispatchStage.Considered, 1, -1) }
        diagnostics.record(17_999, CapacityDispatchStage.TimerLate, 1_800_000_000_000)
        assertEquals(1L, diagnostics.total(CapacityDispatchStage.TimerLate))
    }
}
