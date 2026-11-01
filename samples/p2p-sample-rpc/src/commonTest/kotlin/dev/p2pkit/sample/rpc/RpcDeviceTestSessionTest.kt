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
        session.confirmArchived(failed.runId)
        repeat(110) { index ->
            val result = failed.copy(runId = index.toString(16).padStart(32, '0'))
            session.save(result)
            session.confirmArchived(result.runId)
        }
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

    @Test
    fun everyResultRemainsPendingUntilItsArchiveIsConfirmedEvenAfterRecentListEviction() {
        val session = RpcDeviceTestSession()
        repeat(100) { index -> session.save(failed.copy(runId = index.toString(16).padStart(32, '0'))) }
        assertFalse(session.archiveAvailable)
        assertEquals(100, session.unarchivedReports.size)
        assertFailsWith<IllegalStateException> { session.save(failed) }
        val first = session.unarchivedReports.first()
        session.confirmArchived(first.runId)
        assertTrue(session.archiveAvailable)
        session.save(failed)
        assertEquals(100, session.unarchivedReports.size)
        assertEquals(100, session.reports.size)
        assertTrue(session.unarchivedReports.any { it.runId == failed.runId })
        assertFalse(session.reports.any { it.runId == first.runId })
    }

    @Test
    fun archivedMetadataKeepsDirectionTimeAndObservationsWhileRecentIndexRemainsCompact() {
        val observation = RpcDeviceTestObservation(RpcRequestSide.Client, "qualification.large-echo",
            RpcRequestOutcome.Succeeded, 12, 1_048_576, "HandlerFinished", "Succeeded")
        val report = failed.copy(clientPlatform = "Android", hostPlatform = "iPhone",
            startedAtEpochMillis = 1_793_510_000_000, observations = listOf(observation))
        val session = RpcDeviceTestSession()
        session.save(report)
        val archived = Json.decodeFromString<RpcDeviceTestReport>(session.reportJson(report))
        assertEquals(report, archived)
        assertEquals("Android → iPhone", archived.direction)
        val recent = Json.decodeFromString<List<RpcDeviceTestReport>>(session.exportJson()).single()
        assertEquals(report.copy(observations = emptyList()), recent)
        assertEquals(report, session.unarchivedReports.single())
        session.confirmArchived(report.runId)
        assertTrue(session.unarchivedReports.isEmpty())
        assertEquals(report, session.reports.single(), "Archiving does not erase the displayed result")
    }

    @Test
    fun mirroredResultMustMatchTheRegisteredEndpointMetadataAndInitiator() {
        val begin = DeviceTestBegin(command, "iPhone", 1_793_510_000_000, "Client")
        val result = failed.copy(clientPlatform = "iPhone", hostPlatform = "Mac (JVM)",
            startedAtEpochMillis = begin.startedAtEpochMillis)
        assertTrue(validDeviceTestBegin(begin))
        assertTrue(matchesObservedMetadata(result, begin, "Mac (JVM)"))
        assertTrue(matchesDeviceTestResult("approved-peer", "approved-peer", result, command, begin, "Mac (JVM)"))
        assertFalse(matchesDeviceTestResult("different-peer", "approved-peer", result, command, begin, "Mac (JVM)"))
        for (changed in listOf(result.copy(runId = "c".repeat(32)), result.copy(sourceSha = "c".repeat(40)),
            result.copy(phase = RpcDeviceTestPhase.Correctness))) {
            assertFalse(matchesDeviceTestResult("approved-peer", "approved-peer", changed, command, begin, "Mac (JVM)"))
        }
        assertFalse(matchesObservedMetadata(result, null, "Mac (JVM)"))
        for (changed in listOf(result.copy(clientPlatform = "Android"), result.copy(hostPlatform = "Android"),
            result.copy(startedAtEpochMillis = begin.startedAtEpochMillis + 1), result.copy(initiatedBy = "Host"))) {
            assertFalse(matchesObservedMetadata(changed, begin, "Mac (JVM)"))
        }
        for (changed in listOf(begin.copy(clientPlatform = "Unknown"), begin.copy(clientPlatform = "private address"),
            begin.copy(startedAtEpochMillis = -1), begin.copy(initiatedBy = "Unapproved"))) {
            assertFalse(validDeviceTestBegin(changed))
        }
        assertTrue(validDeviceTestUpdate(DeviceTestUpdate(command, 3, 1, 0)))
        assertFalse(validDeviceTestUpdate(DeviceTestUpdate(command, -1, 1, 0)))
        assertFalse(validDeviceTestUpdate(DeviceTestUpdate(command, 3, 1, 1_800)))
    }

    @Test
    fun activityNeverExportsPayloadOrPeerIdentifiersAndRejectsInventedExecutionEvidence() {
        val history = RpcRequestHistory()
        val session = RpcDeviceTestSession(history)
        val id = history.begin(RpcRequestSide.Client, "qualification.echo", 1,
            "[generated test body; encodedBytes=1024]", requestId = "private-correlation-id",
            peerFingerprint = "private-peer")
        history.finish(id, RpcRequestOutcome.Succeeded, 8, "private response body",
            evidence = dev.p2pkit.rpc.RpcExecutionEvidence.HandlerFinished)
        val observation = session.activity.single()
        assertEquals(1_024, observation.encodedBytes)
        val json = Json.encodeToString(observation)
        assertFalse(json.contains("private"))
        assertTrue(validTestObservation(observation))
        assertFalse(validTestObservation(observation.copy(executionEvidence = "SecretPayload")))
        assertFalse(validTestObservation(observation.copy(clientStage = "ConfirmedRemoteReceipt")))
        assertFalse(validDeviceTestReport(failed.copy(observations = List(33) { observation })))
    }

}
