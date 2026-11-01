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
    @Test
    fun sampledCountersKeepProcessKindsAndChargingSeparate() {
        var window = DeviceResourceWindow(command.runId)
        val charging = RpcPhoneEnvironmentStats(50_000, 400_000, 30_000,
            "charging", "android-battery-manager", "nominal", "android-power-manager")
        window = window.observe(100, 1_000_000_000, 10_000_000, "RESIDENT_BYTES", 20, "NATIVE_THREADS", charging)
        window = window.observe(600, 1_100_000_000, 20_000_000, "RESIDENT_BYTES", 25, "NATIVE_THREADS", charging)
        assertEquals(1, window.summary?.samples, "Subsecond reads do not increase the bounded series")
        window = window.observe(1_100, 1_500_000_000, 30_000_000, "RESIDENT_BYTES", 30, "NATIVE_THREADS", charging)
        val summary = window.summary!!
        assertEquals(50.0, summary.cpuPercentOfOneCore)
        assertEquals(30_000_000, summary.peakMemoryBytes)
        assertEquals(listOf("charging"), summary.batteryStates)
        assertEquals(30_000, summary.peakBatteryTemperatureMilliC)
        assertTrue(validDeviceResources(summary))
        assertFalse(validDeviceResources(summary.copy(memoryKind = "CPU_TEMPERATURE")))
        assertFailsWith<IllegalArgumentException> {
            window.observe(2_100, 1, 30_000_000, "RESIDENT_BYTES", 30, "NATIVE_THREADS", charging)
        }
        val serious = RpcPhoneEnvironmentStats(null, null, null, "unavailable", "unavailable",
            "serious", "ios-process-info")
        window = window.observe(1_101, 1_500_000_000, 30_000_000, "RESIDENT_BYTES", 30, "NATIVE_THREADS", serious)
        assertTrue(window.summary!!.thermalStopped, "Thermal stop is recorded even between normal sample slots")
    }

    @Test
    fun staleCompletionCannotHideAStartingReplacementTest() {
        val session = RpcDeviceTestSession()
        session.publish(RpcDeviceTestProgress("old", "Starting old", true))
        session.publish(RpcDeviceTestProgress("new", "Starting new", true))
        session.finishProgress("old")
        assertTrue(session.progress.running)
        assertEquals("new", session.progress.runId)
        session.finishProgress("new")
        assertFalse(session.progress.running)
    }

}
