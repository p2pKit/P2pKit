package dev.p2pkit.sample.rpc

import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class RpcDeviceTestSessionTest {
    private val command = DeviceTestCommand("a".repeat(32), "b".repeat(40), RpcDeviceTestPhase.Large)
    private val failed = emptyDeviceTestReport(command, "Failed", "InterruptedBeforeMeasurement")

    @Test
    fun openingAndRestoringResultsNeverStartsAWorkload() {
        val session = RpcDeviceTestSession()
        assertFalse(session.progress.running)
        session.restoreJson(Json.encodeToString(listOf(failed)))
        assertEquals(listOf(failed), session.reports)
        assertFalse(session.progress.running)
        assertEquals("INTERACTIVE_CONNECTED_DEVICE_RPC", session.reports.single().scope)
        assertEquals(1, session.reports.single().measuredClientCount)
    }

    @Test
    fun failedResultsStayImmutableAndHistoryIsBounded() {
        val session = RpcDeviceTestSession()
        session.save(failed)
        session.save(failed.copy(status = "Completed"))
        assertEquals("Failed", session.reports.single().status)
        repeat(110) { index -> session.save(failed.copy(runId = index.toString(16).padStart(32, '0'))) }
        assertEquals(100, session.reports.size)
        assertEquals(100, Json.decodeFromString<List<RpcDeviceTestReport>>(session.exportJson()).size)
    }

    @Test
    fun resultAdmissionRejectsFalseCapacityDurationAndCounters() {
        assertTrue(validDeviceTestReport(failed))
        val invalid = listOf(failed.copy(measuredClientCount = 256), failed.copy(sourceSha = "unbound"),
            failed.copy(calls = -1), failed.copy(correctResponses = 1), failed.copy(p99Micros = -1),
            failed.copy(failureCode = "x".repeat(129)), failed.copy(scope = "CAPACITY_QUALIFIED"),
            failed.copy(status = "Completed", phase = RpcDeviceTestPhase.Steady, elapsedMillis = 1_799_999))
        invalid.forEach { assertFalse(validDeviceTestReport(it)) }
        assertFailsWith<IllegalArgumentException> {
            RpcDeviceTestSession().restoreJson(Json.encodeToString(listOf(failed, failed)))
        }
        assertFailsWith<IllegalArgumentException> { RpcDeviceTestSession().restoreJson("x".repeat(512_001)) }
    }
}
