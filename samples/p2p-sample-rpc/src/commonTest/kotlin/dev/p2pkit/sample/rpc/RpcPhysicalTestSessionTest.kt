package dev.p2pkit.sample.rpc

import kotlinx.serialization.json.Json
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class RpcPhysicalTestSessionTest {
    private val source = "a".repeat(40)

    @Test fun catalogCoversEveryOpenPhysicalIssueWithoutResumingDeferredInvestigation() {
        val cases = RpcPhysicalTestCatalog.cases
        assertEquals(cases.size, cases.map { it.id }.distinct().size)
        assertEquals(setOf(21, 23, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
            41, 43, 44, 133, 291, 462, 525), cases.flatMap { it.issues }.toSet())
        assertTrue(cases.all { it.steps.isNotEmpty() && it.equipment.isNotBlank() && it.evidence.isNotBlank() })
        assertEquals(4, cases.count { it.id.startsWith("capacity-") })
        assertTrue(cases.filter { it.id.startsWith("capacity-") }.all { it.phase == null && it.minimumSeconds == 1_800 })
        assertNull(cases.single { it.id == "socket-faults" }.phase)
    }

    @Test fun observationCannotBeDispatchedAsAnRpcWorkloadOrRecordedAsCompleted() {
        val results = RpcDeviceTestSession()
        results.physicalTests.start("core-files", source, "Android")
        val started = results.reports.single()
        assertTrue(validDeviceTestReport(started))
        assertFalse(validDeviceTestCommand(DeviceTestCommand(started.runId, source, RpcDeviceTestPhase.Observation)))
        assertFalse(validDeviceTestReport(started.copy(status = "Completed")))
        assertFalse(validDeviceTestReport(started.copy(calls = 1, correctResponses = 1)))
        assertFalse(validDeviceTestReport(started.copy(physicalObservation = null)))
        assertEquals(0, started.measuredClientCount)
        assertFalse(results.anyTestRunning)
    }

    @Test fun incompleteAndTooShortObservationsCannotBeSubmittedForReview() {
        val results = RpcDeviceTestSession()
        val center = results.physicalTests
        center.start("lan-idle", source, "iPhone")
        assertFailsWith<IllegalStateException> { center.finish("AwaitingReview", "capture", "") }
        RpcPhysicalTestCatalog.find("lan-idle").steps.indices.forEach { center.observeStep(it, true) }
        assertFailsWith<IllegalStateException> { center.finish("AwaitingReview", "capture", "") }
        assertEquals("lan-idle", center.progress?.caseId)
        center.finish("Blocked", "", "Second peer unavailable")
        assertNull(center.progress)
        assertEquals("Blocked", results.reports.last().physicalObservation?.outcome)
    }

    @Test fun checkpointsAndFinalResultsHaveDistinctIdsAndSurviveRoundTrip() {
        val results = RpcDeviceTestSession()
        val center = results.physicalTests
        center.start("core-files", source, "Mac (JVM)")
        val first = results.reports.single()
        center.observeStep(0, true)
        center.checkpoint("private-capture-01", "First transfer recorded")
        RpcPhysicalTestCatalog.find("core-files").steps.indices.forEach { center.observeStep(it, true) }
        assertFailsWith<IllegalArgumentException> { center.finish("AwaitingReview", "", "") }
        center.finish("AwaitingReview", "private-capture-01", "Review both peer files")
        assertEquals(3, results.reports.size)
        assertEquals(3, results.reports.map { it.runId }.distinct().size)
        assertEquals(1, results.reports.map { it.groupId }.distinct().size)
        assertEquals("Started", first.physicalObservation?.outcome)
        assertNotEquals(first.physicalObservation, results.reports.last().physicalObservation)
        assertTrue(results.reports.all { it.status == "NeedsReview" && validDeviceTestReport(it) })
        val restored = RpcDeviceTestSession()
        restored.restoreJson(results.exportJson())
        assertEquals(results.reports, restored.reports)
        assertNull(restored.physicalTests.progress) // Process restart must not restart a workload/timer.
    }

    @Test fun invalidEvidenceAndDuplicateStartsPreserveCurrentRun() {
        val results = RpcDeviceTestSession()
        results.physicalTests.start("ios-backup", source, "iPhone")
        val id = results.physicalTests.progress?.sessionId
        assertFailsWith<IllegalStateException> { results.physicalTests.start("core-files", source, "iPhone") }
        assertFailsWith<IllegalArgumentException> { results.physicalTests.checkpoint("x".repeat(1_025), "") }
        assertFailsWith<IllegalArgumentException> { results.physicalTests.checkpoint("", "😀".repeat(1_025)) }
        assertFailsWith<IllegalArgumentException> { results.physicalTests.observeStep(999, true) }
        assertEquals(id, results.physicalTests.progress?.sessionId)
        assertEquals(1, results.reports.size)
    }

    @Test fun recentExportHasAnExplicitBoundaryAndFailureDoesNotMutateHistory() {
        val results = RpcDeviceTestSession()
        results.physicalTests.start("core-files", source, "Android")
        results.physicalTests.finish("Interrupted", "", "Canceled")
        val lines = mutableListOf<String>()
        results.writeRecentEvidence { lines += it }
        assertEquals(4, lines.size)
        assertTrue(lines.first().contains("\"recentOnly\":true"))
        assertTrue(lines.last().contains("\"exportComplete\":true,\"records\":2"))
        assertEquals(results.reports.first(), Json.decodeFromString<RpcDeviceTestReport>(lines[1]))
        assertFailsWith<IllegalStateException> { results.writeRecentEvidence { error("External provider failed") } }
        assertEquals(2, results.reports.size)
    }

    @Test fun editedArchiveCannotInventStepsOrCapacityAndDoesNotEraseOlderReports() {
        val results = RpcDeviceTestSession()
        results.physicalTests.start("core-files", source, "Android")
        val original = results.reports.single()
        val observation = checkNotNull(original.physicalObservation)
        assertFalse(validDeviceTestReport(original.copy(physicalObservation = observation.copy(observedSteps = listOf(999)))))
        assertFalse(validDeviceTestReport(original.copy(physicalObservation = observation.copy(outcome = "PASS"))))
        assertFalse(validDeviceTestReport(original.copy(physicalObservation = observation.copy(catalogRevision = 99))))
        assertFalse(validDeviceTestReport(original.copy(measuredClientCount = 256)))
        results.restoreJsonRefusalControl(original)
        assertEquals(original, results.reports.single())
    }

    private fun RpcDeviceTestSession.restoreJsonRefusalControl(report: RpcDeviceTestReport) {
        assertFailsWith<IllegalArgumentException> { RpcDeviceTestSession().restoreJson(
            Json.encodeToString(listOf(report.copy(status = "Completed")))) }
    }
}
