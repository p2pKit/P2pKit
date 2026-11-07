package dev.p2pkit.sample.rpc

import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
class RpcSmartTestTest {
    private fun step(rate: Int, correct: Long = rate * 10L, errors: Long = 0, p95: Long = 20_000) =
        RpcSmartTestStep(rate, 1, correct + errors, correct, errors, 0, 0, 10_000,
            10_000, p95, p95, "Measured")

    @Test
    fun errorsTriggerBackoffAndAFreshConfirmationRatherThanAnAssumedMaximum() {
        val search = SmartLoadSearch(RpcSmartTestSettings())
        assertEquals(2, search.consider(step(1)).level?.rps)
        assertNull(search.confirmed)
        val backoff = search.consider(step(2, 10, 10))
        assertEquals(1, backoff.level?.rps)
        assertTrue(backoff.reason.contains("BackOffAndConfirm"))
        assertTrue(search.boundaryObserved)
        assertNull(search.confirmed)
        assertNull(search.consider(step(1)).level)
        assertNotNull(search.confirmed)
    }

    @Test
    fun throughputPlateauWithWorseningLatencyIsDetectedBeforeAnAbsoluteLatencyLimit() {
        val search = SmartLoadSearch(RpcSmartTestSettings())
        search.consider(step(10, 90))
        val result = search.consider(step(20, 91, p95 = 30_000))
        assertTrue(result.reason.contains("ThroughputPlateau"))
        assertEquals(15, result.level?.rps)
        assertNull(search.confirmed)
    }

    @Test
    fun reachedSafetyCeilingIsAConfirmedLowerBoundWithoutAnObservedCapacityBoundary() {
        val search = SmartLoadSearch(RpcSmartTestSettings(maximumSafetyRps = 10))
        assertEquals("ConfirmAtSafetyCeiling", search.consider(step(10)).reason)
        assertFalse(search.boundaryObserved)
        assertNull(search.consider(step(10)).level)
        assertNotNull(search.confirmed)
        assertFalse(search.boundaryObserved)
    }

    @Test
    fun seriousThermalStateStopsImmediatelyAndMissingSensorsDoNotInventMeasurements() {
        val resources = RpcDeviceTestResources(1, 0, 0, 1_048_576, "RESIDENT_BYTES", 10,
            "NATIVE_THREADS", null, null, listOf("unavailable"), listOf("serious"), null, null, null)
        assertEquals("ThermalSafetyStop", resourceSafetyFailure(RpcSmartTestSettings(), resources, null))
        assertNull(resourceSafetyFailure(RpcSmartTestSettings(), null, null))
        val search = SmartLoadSearch(RpcSmartTestSettings())
        assertNull(search.consider(step(1), "ThermalSafetyStop").level)
        assertNull(search.confirmed)
    }

    @Test
    fun measuredWorkersDrainAfterMemoryPressureAndDoNotCreateIndependentClientClaims() = runTest {
        var active = 0
        var maximum = 0
        val output = runSmartTest(RpcSmartTestSettings(stageMillis = 5_000), call = {
            active++
            maximum = maxOf(maximum, active)
            try { delay(100); SmartCall(true, 100_000) } finally { active-- }
        }, clientResources = { null }, hostResources = {
            if (testScheduler.currentTime < 6_000) null else RpcDeviceTestResources(1, 0, 0,
                600L * 1_048_576, "RESIDENT_BYTES", 20, "NATIVE_THREADS", null, null,
                listOf("unavailable"), listOf("nominal"), null, null, null)
        }, progress = { _, _, _ -> }, nowMicros = { testScheduler.currentTime * 1_000 })
        assertEquals(0, active)
        assertEquals(1, maximum)
        assertEquals("MemorySafetyBudgetReached", output.result.stopReason)
        assertTrue(output.result.workerCleanupVerified)
        assertEquals(0, output.result.independentConnectionsCreated)
        assertFalse(output.result.stableLevelConfirmed)
        assertEquals(output.attempts, output.correct + output.failures)
        assertTrue(validSmartResult(output.result))
    }

    @Test
    fun settingsRejectUnboundedConcurrencyAndReportsRejectFalseStableResults() {
        assertFalse(RpcSmartTestSettings(maximumConcurrency = 65).valid())
        assertFalse(RpcSmartTestSettings(maximumErrorPercent = Double.NaN).valid())
        assertFalse(validSmartStep(step(1).copy(attempts = 1, correct = 2)))
        val result = RpcSmartTestResult(RpcSmartTestSettings(), emptyList(), 0.0, 0.0, 0,
            "NoStableLevelFound", false, false, true)
        assertTrue(validSmartResult(result))
        assertFalse(validSmartResult(result.copy(stableLevelConfirmed = true)))
        assertFalse(validSmartResult(result.copy(independentConnectionsCreated = 256)))
    }
    @Test
    fun anUnstableConfirmationReducesLoadAndRequiresFreshEvidence() {
        val search = SmartLoadSearch(RpcSmartTestSettings())
        search.consider(step(4))
        search.consider(step(8, 10, 70))
        search.consider(step(6, 10, 50))
        search.consider(step(5, 10, 40))
        val reduced = search.consider(step(4, 10, 30))
        assertEquals(2, reduced.level?.rps)
        assertTrue(reduced.reason.contains("ConfirmationUnstable"))
        assertNull(search.confirmed)
        assertNotNull(search.consider(step(2)).level)
        assertNull(search.confirmed, "A single backoff sample must not become a confirmed result")
    }

    @Test
    fun cancellationStopsAndJoinsEveryWorkerAndRetainsPartialCounts() = runTest {
        var active = 0
        var output: SmartRunOutput? = null
        val job = launch {
            output = runSmartTest(RpcSmartTestSettings(stageMillis = 5_000), call = {
                active++
                try { delay(2_000); SmartCall(true, 2_000_000) } finally { active-- }
            }, clientResources = { null }, hostResources = { null }, progress = { _, _, _ -> },
                nowMicros = { testScheduler.currentTime * 1_000 })
        }
        testScheduler.advanceTimeBy(1_100)
        job.cancelAndJoin()
        assertEquals(0, active)
        val result = assertNotNull(output)
        assertEquals("CallerCancelled", result.result.stopReason)
        assertEquals(result.attempts, result.correct + result.failures)
        assertTrue(result.result.workerCleanupVerified)
        assertFalse(result.result.stableLevelConfirmed)
    }

    @Test
    fun repeatedTimeoutsWithoutAReplyStopBeforeAnotherGrowthStage() = runTest {
        val output = runSmartTest(RpcSmartTestSettings(stageMillis = 5_000), call = {
            delay(10); SmartCall(false, 10_000, timeout = true)
        }, clientResources = { null }, hostResources = { null }, progress = { _, _, _ -> },
            nowMicros = { testScheduler.currentTime * 1_000 })
        assertEquals("HostUnresponsive", output.result.stopReason)
        assertEquals(3L, output.failures)
        assertEquals(1, output.result.steps.size)
        assertTrue(output.result.workerCleanupVerified)
    }

}
