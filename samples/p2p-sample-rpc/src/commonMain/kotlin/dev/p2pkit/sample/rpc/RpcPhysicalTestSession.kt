package dev.p2pkit.sample.rpc

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.Serializable
import kotlin.time.Clock
import kotlin.time.TimeSource

/** Operator testimony stays separate from measured RPC success and independent evidence review. */
@Serializable
public data class RpcPhysicalTestObservation(
    public val catalogRevision: Int,
    public val caseId: String,
    public val sessionId: String,
    public val outcome: String,
    public val observedSteps: List<Int>,
    public val evidenceReference: String,
    public val notes: String,
    public val requiredSeconds: Int,
    public val observedMillis: Long,
) {
    public val title: String get() = "${RpcPhysicalTestCatalog.find(caseId).title} · $outcome"
    public val detail: String get() = buildString {
        appendLine("Observation group: $sessionId · catalog $catalogRevision")
        appendLine("Observed ${observedMillis / 1_000}s; required observation ${requiredSeconds}s")
        appendLine("Steps marked observed: ${observedSteps.joinToString { (it + 1).toString() }}")
        appendLine("Evidence reference (operator supplied): ${evidenceReference.ifEmpty { "Not supplied" }}")
        appendLine(notes)
        appendLine("Operator observations require independent evidence review; this record is not a qualification PASS.")
    }
}

public data class RpcPhysicalTestProgress(
    public val sessionId: String,
    public val caseId: String,
    public val observedSteps: List<Int> = emptyList(),
) {
    public val testCase: RpcPhysicalTestCase get() = RpcPhysicalTestCatalog.find(caseId)
}

/** Each checkpoint is a new immutable archive record, grouped by one observation session. */
public class RpcPhysicalTestSession internal constructor(private val results: RpcDeviceTestSession) {
    private data class Active(
        val progress: RpcPhysicalTestProgress,
        val source: String,
        val platform: String,
        val started: Long,
        val clock: TimeSource.Monotonic.ValueTimeMark,
    )
    private var active: Active? = null
    private val state = MutableStateFlow<RpcPhysicalTestProgress?>(null)
    public val changes = state.asStateFlow()
    public val progress: RpcPhysicalTestProgress? get() = state.value
    public val elapsedMillis: Long get() = active?.clock?.elapsedNow()?.inWholeMilliseconds ?: 0

    @Throws(Exception::class)
    public fun start(caseId: String, source: String, platform: String) {
        check(active == null && !results.anyTestRunning && results.archiveAvailable && !results.resultDeletionInProgress)
        require(source.matches(Regex("[a-f0-9]{40}")) && platform in deviceTestPlatforms && platform != "Unknown")
        val test = RpcPhysicalTestCatalog.find(caseId)
        require(test.phase == null) { "Use the built-in workload button for an automated RPC case" }
        val progress = RpcPhysicalTestProgress(newDeviceTestId(), caseId)
        val started = Clock.System.now().toEpochMilliseconds()
        require(started in 1..4_102_444_800_000)
        results.beginResources(progress.sessionId)
        active = Active(progress, source, platform, started, TimeSource.Monotonic.markNow())
        try {
            save("Started", "", "No test result yet. Missing hardware or tooling is not supplied by this guide.")
        } catch (failure: Exception) {
            results.finishResources(progress.sessionId)
            active = null
            throw failure
        }
        state.value = progress
    }

    @Throws(Exception::class)
    public fun observeStep(index: Int, observed: Boolean) {
        val current = checkNotNull(active)
        require(index in current.progress.testCase.steps.indices)
        val steps = if (observed) (current.progress.observedSteps + index).distinct().sorted()
            else current.progress.observedSteps - index
        active = current.copy(progress = current.progress.copy(observedSteps = steps))
        state.value = checkNotNull(active).progress
    }

    @Throws(Exception::class)
    public fun checkpoint(evidenceReference: String, notes: String) {
        save("Checkpoint", evidenceReference, notes)
    }

    /** No manual PASS control: even a complete operator observation is AwaitingReview. */
    @Throws(Exception::class)
    public fun finish(outcome: String, evidenceReference: String, notes: String) {
        require(outcome in setOf("AwaitingReview", "Failed", "Blocked", "Interrupted"))
        val current = checkNotNull(active)
        if (outcome == "AwaitingReview") {
            check(current.progress.observedSteps.size == current.progress.testCase.steps.size)
            check(elapsedMillis >= current.progress.testCase.minimumSeconds * 1_000L)
            require(evidenceReference.isNotBlank())
        }
        save(outcome, evidenceReference, notes)
        results.finishResources(current.progress.sessionId)
        active = null
        state.value = null
    }

    private fun save(outcome: String, reference: String, notes: String) {
        val current = checkNotNull(active)
        val now = Clock.System.now().toEpochMilliseconds().coerceAtLeast(current.started)
        val elapsed = elapsedMillis
        val test = current.progress.testCase
        val observation = RpcPhysicalTestObservation(RpcPhysicalTestCatalog.revision, test.id,
            current.progress.sessionId, outcome, current.progress.observedSteps, reference, notes,
            test.minimumSeconds, elapsed)
        require(validPhysicalObservation(observation))
        val report = RpcDeviceTestReport(newDeviceTestId(), RpcDeviceTestPhase.Observation, current.source,
            "NeedsReview", 0, 0, elapsed, 0, 0, 0, 0, 0, 0, 0, null,
            measuredClientCount = 0, scope = "PHYSICAL_TEST_OPERATOR_OBSERVATION",
            clientPlatform = current.platform, startedAtEpochMillis = current.started, endedAtEpochMillis = now,
            initiatedBy = "Operator", mode = "Guided", groupId = observation.sessionId,
            clientResources = results.resources(current.progress.sessionId), physicalObservation = observation)
        results.save(report)
    }
}

internal fun validPhysicalObservation(value: RpcPhysicalTestObservation): Boolean {
    val test = RpcPhysicalTestCatalog.cases.firstOrNull { it.id == value.caseId } ?: return false
    return value.catalogRevision == RpcPhysicalTestCatalog.revision && test.phase == null &&
        value.sessionId.matches(Regex("[a-f0-9]{32}")) &&
        value.outcome in setOf("Started", "Checkpoint", "AwaitingReview", "Failed", "Blocked", "Interrupted") &&
        value.observedSteps.size <= test.steps.size && value.observedSteps.distinct() == value.observedSteps &&
        value.observedSteps.all { it in test.steps.indices } && value.requiredSeconds == test.minimumSeconds &&
        value.observedMillis in 0..86_400_000 && value.evidenceReference.encodeToByteArray().size <= 1_024 &&
        value.notes.encodeToByteArray().size <= 4_096 &&
        (value.outcome != "AwaitingReview" || value.observedSteps.size == test.steps.size &&
            value.evidenceReference.isNotBlank() && value.observedMillis >= test.minimumSeconds * 1_000L)
}

internal fun validPhysicalTestReport(value: RpcDeviceTestReport): Boolean =
    value.physicalObservation?.let { observation ->
        validPhysicalObservation(observation) && value.phase == RpcDeviceTestPhase.Observation &&
            value.runId.matches(Regex("[a-f0-9]{32}")) && value.sourceSha.matches(Regex("[a-f0-9]{40}")) &&
            value.scope == "PHYSICAL_TEST_OPERATOR_OBSERVATION" && value.mode == "Guided" &&
            value.status == "NeedsReview" && value.initiatedBy == "Operator" &&
            value.groupId == observation.sessionId && value.clientPlatform in deviceTestPlatforms &&
            value.clientPlatform != "Unknown" && value.hostPlatform == "Unknown" &&
            value.startedAtEpochMillis in 1..4_102_444_800_000 &&
            value.endedAtEpochMillis in value.startedAtEpochMillis..4_102_444_800_000 &&
            value.elapsedMillis == observation.observedMillis && value.initializationMillis == 0L &&
            value.measuredClientCount == 0 && value.calls == 0L && value.correctResponses == 0L &&
            value.failedResponses == 0L && value.missedSchedules == 0L && value.failureCode == null &&
            value.p50Micros == 0L && value.p95Micros == 0L && value.p99Micros == 0L &&
            value.deliberateDisconnects == 0 && value.expectedDeadlines == 0 && value.callerCancellations == 0 &&
            value.latencySamples == 0L && value.latencyBucketMicros == 1_000 &&
            value.observations.isEmpty() && value.smart == null && value.progressMessages == 0L &&
            value.telemetryMessages == 0L && value.initiatingHostResources == null &&
            validDeviceResources(value.clientResources, longObservation = true)
    } ?: false
