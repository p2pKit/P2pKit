package dev.p2pkit.sample.rpc

import kotlinx.serialization.Serializable
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min

/** Automatic defaults; ceilings are safety budgets, never a claimed capacity result. */
@Serializable
public data class RpcSmartTestSettings(
    public val stageMillis: Long = 10_000,
    public val maximumMillis: Long = 600_000,
    public val maximumConcurrency: Int = 64,
    public val maximumSafetyRps: Int = 5_000,
    public val p95LimitMillis: Int = 1_000,
    public val p99LimitMillis: Int = 2_000,
    public val maximumErrorPercent: Double = 1.0,
    public val maximumMissedPercent: Double = 10.0,
    public val maximumMemoryBytes: Long = 536_870_912,
    public val maximumNativeThreads: Int = 512,
) {
    public fun valid(): Boolean = stageMillis in 5_000..30_000 && maximumMillis in 60_000..900_000 &&
        maximumConcurrency in 1..64 && maximumSafetyRps in 10..5_000 &&
        p95LimitMillis in 50..5_000 && p99LimitMillis in p95LimitMillis..10_000 &&
        maximumErrorPercent.isFinite() && maximumErrorPercent in 0.0..5.0 &&
        maximumMissedPercent.isFinite() && maximumMissedPercent in 0.0..25.0 &&
        maximumMemoryBytes in 134_217_728..2_147_483_648 && maximumNativeThreads in 64..1_024
}

@Serializable
public data class RpcSmartTestStep(
    public val targetRps: Int,
    public val concurrency: Int,
    public val attempts: Long,
    public val correct: Long,
    public val errors: Long,
    public val timeouts: Long,
    public val missed: Long,
    public val elapsedMillis: Long,
    public val p50Micros: Long,
    public val p95Micros: Long,
    public val p99Micros: Long,
    public val decision: String,
    public val clientMemoryBytes: Long? = null,
    public val hostMemoryBytes: Long? = null,
    public val clientResources: RpcDeviceTestResources? = null,
    public val hostResources: RpcDeviceTestResources? = null,
) {
    public val throughputRps: Double get() = if (elapsedMillis > 0) correct * 1_000.0 / elapsedMillis else 0.0
    public val title: String get() = "$targetRps target/s · concurrency $concurrency · " +
        "${(throughputRps * 10).toLong() / 10.0} correct/s · p95 ${p95Micros / 1_000} ms · $decision"
}

@Serializable
public data class RpcSmartTestResult(
    public val settings: RpcSmartTestSettings,
    public val steps: List<RpcSmartTestStep>,
    public val maximumObservedRps: Double,
    public val highestConfirmedStableRps: Double,
    public val stableConcurrency: Int,
    public val stopReason: String,
    public val boundaryObserved: Boolean,
    public val stableLevelConfirmed: Boolean,
    public val workerCleanupVerified: Boolean,
    public val independentConnectionsCreated: Int = 0,
    public val connectionPressureScope: String = "EXISTING_AUTHENTICATED_DEVICE_CONNECTION",
    public val highestConfirmedTargetRps: Int = 0,
    public val measurementScope: String = "CONNECTED_CLIENT_TO_HOST_PATH",
    public val limitations: List<String> = emptyList(),
) {
    public val title: String get() = "Observed ${(maximumObservedRps * 10).toLong() / 10.0} correct/s · " +
        "confirmed stable ${(highestConfirmedStableRps * 10).toLong() / 10.0} correct/s · " +
        "concurrency $stableConcurrency · $stopReason"
}

internal data class SmartLevel(val rps: Int, val concurrency: Int)
internal data class SmartDecision(val level: SmartLevel?, val reason: String, val stable: Boolean)

/** Bracket growth, back off on instability, then confirm the last stable point on a fresh stage. */
internal class SmartLoadSearch(private val settings: RpcSmartTestSettings) {
    private var lower: SmartLevel? = null
    private var upper: SmartLevel? = null
    private var previous: RpcSmartTestStep? = null
    private var baselineP95: Long? = null
    private var confirming = false
    private var refinements = 0
    var boundaryObserved = false
        private set
    var confirmed: RpcSmartTestStep? = null
        private set

    fun consider(step: RpcSmartTestStep, fatal: String? = null): SmartDecision {
        require(validSmartStep(step))
        fatal?.let { return SmartDecision(null, it, false) }
        val latencyLimit = min(settings.p95LimitMillis * 1_000L,
            max(100_000L, (baselineP95 ?: step.p95Micros) * 4))
        val errorPercent = if (step.attempts > 0) step.errors * 100.0 / step.attempts else 100.0
        val missedPercent = step.missed * 100.0 / max(1, step.attempts + step.missed)
        val plateau = previous?.let { old ->
            step.targetRps > old.targetRps && step.throughputRps < old.throughputRps * 1.05 &&
                (step.p95Micros > old.p95Micros * 1.25 || missedPercent > 1.0)
        } == true
        val unstable = step.correct == 0L || errorPercent > settings.maximumErrorPercent ||
            missedPercent > settings.maximumMissedPercent || step.p95Micros > latencyLimit ||
            step.p99Micros > settings.p99LimitMillis * 1_000L || plateau
        val current = SmartLevel(step.targetRps, step.concurrency)
        if (unstable) {
            boundaryObserved = true
            upper = current
            val failedConfirmation = confirming
            confirming = false
            var stable = lower ?: return SmartDecision(null, "NoStableLevelFound", false)
            if (failedConfirmation) {
                if (current.rps <= 1) return SmartDecision(null, "NoStableLevelFound", false)
                stable = SmartLevel(max(1, current.rps / 2), max(1, current.concurrency / 2))
                lower = null // A formerly stable level is no longer confirmed; measure the backoff afresh.
                previous = null
                return SmartDecision(stable, "ConfirmationUnstable/ReduceAndRemeasure", false)
            }
            val reason = when {
                plateau -> "ThroughputPlateau"
                errorPercent > settings.maximumErrorPercent -> "ErrorOrTimeoutGrowth"
                missedPercent > settings.maximumMissedPercent -> "SchedulingPressure"
                else -> "LatencyDeterioration"
            }
            if (current.rps - stable.rps <= max(1, stable.rps / 10) || refinements++ >= 4) {
                confirming = true
                return SmartDecision(stable, "BackOffAndConfirm/$reason", false)
            }
            val rps = (current.rps + stable.rps) / 2
            return SmartDecision(SmartLevel(rps, max(stable.concurrency,
                ceil(rps * max(1_000L, stableLatency()) / 1_000_000.0 * 1.5).toInt())
                .coerceAtMost(settings.maximumConcurrency)), "BackOff/$reason", false)
        }
        if (confirming) {
            confirmed = step
            return SmartDecision(null, "StableBoundaryConfirmed", true)
        }
        baselineP95 = baselineP95 ?: step.p95Micros
        lower = current
        previous = step
        val high = upper
        if (high != null) {
            if (high.rps - current.rps <= max(1, current.rps / 10) || refinements++ >= 4) {
                confirming = true
                return SmartDecision(current, "ConfirmStableLevel", true)
            }
            val rps = (high.rps + current.rps) / 2
            return SmartDecision(SmartLevel(rps, min(settings.maximumConcurrency,
                max(current.concurrency, ceil(rps * stableLatency() / 1_000_000.0 * 1.5).toInt()))),
                "RefineStableBoundary", true)
        }
        if (current.rps >= settings.maximumSafetyRps) {
            confirming = true
            upper = current
            return SmartDecision(current, "ConfirmAtSafetyCeiling", true)
        }
        val rps = min(settings.maximumSafetyRps, max(current.rps + 1, current.rps * 2))
        return SmartDecision(SmartLevel(rps, min(settings.maximumConcurrency,
            max(current.concurrency, ceil(rps * stableLatency() / 1_000_000.0 * 1.5).toInt()))),
            "IncreaseLoad", true)
    }

    private fun stableLatency(): Long = max(1_000L, previous?.p95Micros ?: 1_000L)
}

internal fun validSmartStep(step: RpcSmartTestStep): Boolean = step.targetRps in 1..5_000 &&
    step.concurrency in 1..64 && step.attempts in 0..1_000_000 && step.correct in 0..step.attempts &&
    step.errors in 0..step.attempts && step.correct + step.errors == step.attempts &&
    step.timeouts in 0..step.errors && step.missed in 0..1_000_000 && step.elapsedMillis in 1..60_000 &&
    step.p50Micros in 0..step.p95Micros && step.p95Micros in 0..step.p99Micros &&
    step.p99Micros in 0..30_001_000 && step.decision.length <= 96 &&
    listOfNotNull(step.clientMemoryBytes, step.hostMemoryBytes).all { it in 1..68_719_476_736 } &&
    validDeviceResources(step.clientResources) && validDeviceResources(step.hostResources)

internal fun validSmartResult(result: RpcSmartTestResult?): Boolean = result == null ||
    (result.settings.valid() && result.steps.size <= 24 && result.steps.all(::validSmartStep) &&
        result.maximumObservedRps.isFinite() && result.maximumObservedRps >= 0 &&
        result.highestConfirmedStableRps.isFinite() && result.highestConfirmedStableRps in
        0.0..result.maximumObservedRps && result.stableConcurrency in 0..64 && result.stopReason.length <= 96 &&
        result.independentConnectionsCreated == 0 &&
        result.connectionPressureScope == "EXISTING_AUTHENTICATED_DEVICE_CONNECTION" &&
        result.highestConfirmedTargetRps in 0..5_000 && result.measurementScope == "CONNECTED_CLIENT_TO_HOST_PATH" &&
        result.limitations.size <= 8 && result.limitations.all { it.length <= 160 } &&
        (!result.stableLevelConfirmed || result.highestConfirmedStableRps > 0))
