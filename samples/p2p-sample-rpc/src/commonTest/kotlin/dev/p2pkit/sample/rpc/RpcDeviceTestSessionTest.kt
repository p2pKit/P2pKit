package dev.p2pkit.sample.rpc

import kotlinx.serialization.json.Json
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class RpcDeviceTestSessionTest {
    private val command = DeviceTestCommand("a".repeat(32), "b".repeat(40), RpcDeviceTestPhase.Large)
    private val failed = emptyDeviceTestReport(command, "Failed", "InterruptedBeforeMeasurement")

    @Test
    fun multiAdmissionKeepsPairIsolationAndOneActiveRunPerApprovedClient() {
        val multi = command.copy(mode = "Multi", groupId = "c".repeat(32))
        val active = listOf("peer-one" to multi)
        assertTrue(deviceTestAdmission(true, active, "peer-two", multi.copy(runId = "d".repeat(32))))
        assertFalse(deviceTestAdmission(false, active, "peer-two", multi.copy(runId = "d".repeat(32))))
        assertFalse(deviceTestAdmission(true, active, "peer-one", multi.copy(runId = "d".repeat(32))))
        assertFalse(deviceTestAdmission(true, active, "peer-two", command.copy(runId = "d".repeat(32))))
        assertFalse(deviceTestAdmission(true, active, "peer-two", multi))
        val full = (0 until DEVICE_TEST_MAX_PARALLEL).map { "$it" to multi }
        assertFalse(deviceTestAdmission(true, full, "new", multi.copy(runId = "d".repeat(32))))
    }

    @Test
    fun completingOneClientDoesNotClearAnotherAndDisplayClearRetainsRealEvidence() {
        val history = RpcRequestHistory()
        val session = RpcDeviceTestSession(history)
        session.publish(RpcDeviceTestProgress("one", "First", true))
        session.publish(RpcDeviceTestProgress("two", "Second", true))
        session.finishProgress("one")
        assertEquals(listOf("two"), session.activeTests.map { it.runId })
        assertTrue(session.anyTestRunning)
        session.finishProgress("two")
        session.save(failed)
        val id = history.begin(RpcRequestSide.Client, "qualification.echo", 1, "[test body omitted]")
        history.finish(id, RpcRequestOutcome.Succeeded, 1, "[reply omitted]")
        val archived = session.reportJson(failed)
        val realHistory = history.entries()
        session.clearDisplayedActivity()
        assertTrue(session.activity.isEmpty())
        assertTrue(session.displayedReports.isEmpty())
        assertEquals(realHistory, history.entries())
        assertEquals(archived, session.reportJson(session.reports.single()))
        session.showSavedResults()
        assertEquals(listOf(failed), session.displayedReports)
    }

    @Test
    fun deletionRequiresFinishedArchivedOutputAndCannotDeleteAnotherRun() = runTest {
        val session = RpcDeviceTestSession()
        session.save(failed)
        assertFalse(session.beginResultDeletion(failed.runId))
        session.confirmArchived(failed.runId)
        session.publish(RpcDeviceTestProgress("active", "Active", true))
        assertFalse(session.beginResultDeletion(failed.runId))
        session.finishProgress("active")
        assertTrue(session.beginResultDeletion(failed.runId))
        assertFailsWith<IllegalStateException> { session.finishResultDeletion("d".repeat(32), true) }
        session.finishResultDeletion(failed.runId, false)
        assertEquals(listOf(failed), session.reports)
        assertTrue(session.beginResultDeletion(failed.runId))
        session.finishResultDeletion(failed.runId, true)
        assertTrue(session.reports.isEmpty())
        assertFalse(session.resultDeletionInProgress)
    }

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
        session.save(failed.copy(status = "Completed", calls = 3, correctResponses = 3, failureCode = null))
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
        assertFailsWith<IllegalArgumentException> { RpcDeviceTestSession().restoreJson("x".repeat(8_388_609)) }
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
    fun compactIndexReopenPreservesRicherArchiveAndStillRejectsChangedMeasurements() {
        val observation = RpcDeviceTestObservation(RpcRequestSide.Client, "qualification.echo",
            RpcRequestOutcome.Succeeded, 12, 1_024, "HandlerFinished", "Succeeded")
        val report = failed.copy(observations = listOf(observation), clientPlatform = "iPhone",
            hostPlatform = "Mac (JVM)", startedAtEpochMillis = 1_793_510_000_000)
        val initial = RpcDeviceTestSession()
        initial.save(report)
        val archive = initial.reportJson(report)
        val restored = RpcDeviceTestSession()
        restored.restoreJson(initial.exportJson())
        val compact = restored.unarchivedReports.single()
        assertTrue(compact.observations.isEmpty())
        assertTrue(restored.archiveMatches(compact, archive))
        assertFalse(restored.archiveMatches(compact, initial.reportJson(report.copy(elapsedMillis = 1))))
        assertFalse(restored.archiveMatches(compact, "invalid JSON"))
        val fresh = RpcDeviceTestSession()
        fresh.save(compact)
        assertFalse(fresh.archiveMatches(compact, archive), "Only a restored index can omit archived observations")
        restored.confirmArchived(compact.runId)
        assertTrue(restored.unarchivedReports.isEmpty())
        assertFalse(restored.archiveMatches(compact, archive), "Restore allowance ends after archive confirmation")
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

    @Test
    fun perRunResourceWindowsRemainSeparateAndCompletionKeepsOtherSamples() {
        val session = RpcDeviceTestSession()
        session.beginResources("first")
        session.observeResources(1_000_000, 10_000_000, "RESIDENT_BYTES", 10, "NATIVE_THREADS", null)
        session.beginResources("second")
        session.observeResources(2_000_000, 20_000_000, "RESIDENT_BYTES", 20, "NATIVE_THREADS", null)
        assertEquals(10_000_000, session.finishResources("first")?.peakMemoryBytes)
        assertEquals(20_000_000, session.resources("second")?.peakMemoryBytes)
        assertEquals(20_000_000, session.finishResources("second")?.peakMemoryBytes)
    }

    @Test
    fun groupMetadataCannotBeReassignedToAnotherRunOrPeer() {
        val multi = command.copy(mode = "Multi", groupId = "c".repeat(32))
        val begin = DeviceTestBegin(multi, "Android", 1_793_510_000_000, "Host")
        val result = failed.copy(mode = "Multi", groupId = multi.groupId, clientPlatform = "Android",
            hostPlatform = "iPhone", startedAtEpochMillis = begin.startedAtEpochMillis, initiatedBy = "Host")
        assertTrue(matchesDeviceTestResult("peer", "peer", result, multi, begin, "iPhone"))
        assertFalse(matchesDeviceTestResult("another", "peer", result, multi, begin, "iPhone"))
        assertFalse(matchesDeviceTestResult("peer", "peer", result.copy(groupId = "d".repeat(32)), multi, begin, "iPhone"))
        assertFalse(matchesDeviceTestResult("peer", "peer", result.copy(mode = "Pair"), multi, begin, "iPhone"))
    }

    @Test
    fun smartStagesAreArchivedSeparatelyAndHydratedAfterCompactIndexReopen() {
        val settings = RpcSmartTestSettings()
        val step = RpcSmartTestStep(10, 1, 100, 100, 0, 0, 0, 10_000, 10_000, 20_000, 30_000,
            "StableBoundaryConfirmed")
        val smart = RpcSmartTestResult(settings, listOf(step), 10.0, 10.0, 1,
            "StableBoundaryConfirmed", true, true, true, highestConfirmedTargetRps = 10)
        val result = failed.copy(phase = RpcDeviceTestPhase.Adaptive, status = "Completed", calls = 100,
            correctResponses = 100, failureCode = null, smart = smart)
        val original = RpcDeviceTestSession()
        original.save(result)
        val archive = original.reportJson(result)
        val reopened = RpcDeviceTestSession()
        reopened.restoreJson(original.exportJson())
        assertTrue(reopened.reports.single().smart!!.steps.isEmpty())
        reopened.hydrateArchived(reopened.unarchivedReports.single(), archive)
        assertEquals(result, reopened.reports.single())
        assertTrue(archive.toByteArray().size <= 65_536)
        val many = RpcDeviceTestSession()
        repeat(100) { index ->
            val report = result.copy(runId = index.toString(16).padStart(32, '0'))
            many.save(report)
            many.confirmArchived(report.runId)
        }
        assertTrue(many.exportJson().toByteArray().size <= 262_100, "Recent index fits one encrypted vault record")
    }

}
