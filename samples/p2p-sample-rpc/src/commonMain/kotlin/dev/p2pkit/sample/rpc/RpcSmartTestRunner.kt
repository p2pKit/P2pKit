package dev.p2pkit.sample.rpc

import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.yield
import kotlin.math.max
import kotlin.time.TimeSource

internal data class SmartCall(val correct: Boolean, val micros: Long, val timeout: Boolean = false,
    val fatal: String? = null)
internal data class SmartRunOutput(val result: RpcSmartTestResult, val attempts: Long, val correct: Long,
    val failures: Long, val missed: Long, val buckets: LongArray)

internal class SmartStageCounters(private val attemptsBefore: Long = 0, private val correctBefore: Long = 0,
    private val failuresBefore: Long = 0) {
    val lock = Mutex()
    val buckets = LongArray(30_001)
    var attempts = 0L
    var correct = 0L
    var failures = 0L
    var timeouts = 0L
    var missed = 0L
    var inFlight = 0
    var peakInFlight = 0
    var fatal: String? = null
    val totalAttempts: Long get() = attemptsBefore + attempts
    val totalCorrect: Long get() = correctBefore + correct
    val totalFailures: Long get() = failuresBefore + failures
}

internal fun smartPercentile(buckets: LongArray, samples: Long, percent: Int): Long {
    if (samples == 0L) return 0
    val target = (samples * percent + 99) / 100
    var sum = 0L
    for (index in buckets.indices) {
        sum += buckets[index]
        if (sum >= target) return (index + 1L) * 1_000
    }
    return 30_001_000
}

/** A bounded worker pool adds in-flight pressure, never identities or independent socket claims. */
internal suspend fun runSmartTest(
    settings: RpcSmartTestSettings,
    call: suspend () -> SmartCall,
    clientResources: () -> RpcDeviceTestResources?,
    hostResources: () -> RpcDeviceTestResources?,
    progress: (SmartLevel, SmartStageCounters, String) -> Unit,
    nowMicros: (() -> Long)? = null,
): SmartRunOutput {
    require(settings.valid())
    val origin = TimeSource.Monotonic.markNow()
    val now = nowMicros ?: { origin.elapsedNow().inWholeMicroseconds }
    val search = SmartLoadSearch(settings)
    val steps = mutableListOf<RpcSmartTestStep>()
    val aggregate = LongArray(30_001)
    var attempts = 0L
    var correct = 0L
    var failures = 0L
    var missed = 0L
    var level = SmartLevel(1, 1)
    var stop = "StageBudgetReached"
    var maximum = 0.0
    val started = now()
    for (stage in 0 until 24) {
        if (now() - started >= settings.maximumMillis * 1_000) { stop = "TimeSafetyBudgetReached"; break }
        val counters = SmartStageCounters(attempts, correct, failures)
        val startedStage = now()
        var cancelled = false
        try {
            coroutineScope {
                val permits = Channel<Unit>(Channel.RENDEZVOUS)
                val workers = List(level.concurrency) {
                    launch {
                        for (permit in permits) {
                            counters.lock.withLock {
                                counters.attempts++
                                counters.inFlight++
                                counters.peakInFlight = max(counters.peakInFlight, counters.inFlight)
                            }
                            val result = try { call() }
                            catch (failure: CancellationException) {
                                counters.lock.withLock { counters.failures++; counters.inFlight-- }
                                throw failure
                            }
                            catch (_: Exception) { SmartCall(false, 0, fatal = "LocalCallFailure") }
                            counters.lock.withLock {
                                counters.inFlight--
                                if (result.correct) {
                                    counters.correct++
                                    counters.buckets[(result.micros / 1_000).coerceIn(0, 30_000).toInt()]++
                                } else counters.failures++
                                if (result.timeout) counters.timeouts++
                                if (result.fatal != null) counters.fatal = result.fatal
                                if (counters.timeouts >= 3 && counters.correct == 0L) {
                                    counters.fatal = "HostUnresponsive"
                                }
                            }
                        }
                    }
                }
                val end = startedStage + settings.stageMillis * 1_000
                val interval = 1_000_000L / level.rps
                var next = startedStage
                var lastProgress = startedStage - 1_000_000
                try {
                    yield() // Admit ready workers before the first scheduled offer.
                    while (now() < end && now() - started < settings.maximumMillis * 1_000) {
                        val instant = now()
                        resourceSafetyFailure(settings, clientResources(), hostResources())?.let { cause ->
                            counters.lock.withLock { counters.fatal = cause }
                        }
                        if (counters.lock.withLock { counters.fatal != null }) break
                        if (counters.lock.withLock { counters.totalAttempts >= 1_000_000 || counters.missed >= 1_000_000 }) {
                            counters.fatal = "RequestSafetyBudgetReached"
                            break
                        }
                        if (instant < next) {
                            delay(max(1, (next - instant + 999) / 1_000))
                            continue
                        }
                        val skipped = ((instant - next) / interval).coerceAtLeast(0)
                        next += (skipped + 1) * interval
                        counters.lock.withLock { counters.missed += skipped }
                        if (!permits.trySend(Unit).isSuccess) counters.lock.withLock { counters.missed++ }
                        if (instant - lastProgress >= 1_000_000) {
                            counters.lock.withLock { progress(level, counters, "Measuring adaptive stage ${stage + 1}") }
                            lastProgress = instant
                        }
                        yield()
                    }
                } finally {
                    permits.close()
                    withContext(NonCancellable) {
                        if (counters.fatal != null) workers.forEach { it.cancelAndJoin() }
                        else workers.forEach { it.join() }
                    }
                }
            }
        } catch (_: CancellationException) { cancelled = true }
        val elapsed = ((now() - startedStage) / 1_000).coerceAtLeast(1)
        val raw = RpcSmartTestStep(level.rps, level.concurrency, counters.attempts, counters.correct,
            counters.failures, counters.timeouts, counters.missed, elapsed,
            smartPercentile(counters.buckets, counters.correct, 50),
            smartPercentile(counters.buckets, counters.correct, 95),
            smartPercentile(counters.buckets, counters.correct, 99), "Measured",
            clientResources()?.peakMemoryBytes, hostResources()?.peakMemoryBytes,
            clientResources(), hostResources(), counters.peakInFlight)
        val decision = search.consider(raw, if (cancelled) "CallerCancelled" else counters.fatal)
        steps += raw.copy(decision = decision.reason)
        progress(level, counters, decision.reason)
        attempts += counters.attempts
        correct += counters.correct
        failures += counters.failures
        missed += counters.missed
        counters.buckets.forEachIndexed { index, count -> aggregate[index] += count }
        maximum = max(maximum, raw.throughputRps)
        stop = decision.reason
        val replacement = decision.level ?: break
        level = replacement
        if (attempts >= 1_000_000) { stop = "RequestSafetyBudgetReached"; break }
        if (stage == 23) stop = "StageBudgetReached"
    }
    if (search.confirmed != null && !search.boundaryObserved) stop = "SafetyCeilingConfirmed/LowerBoundOnly"
    val stable = search.confirmed
    val limitations = mutableListOf("Request concurrency uses the existing authenticated connection; no new clients.",
        "Worker drain verified; the application role connection remains open until Stop.",
        "A stable result describes this measured Client-to-Host path, not an absolute Host capacity.")
    if (hostResources() == null) limitations += "Host resource telemetry unavailable; Host resource safety unverified."
    if (clientResources() == null) limitations += "Client resource telemetry unavailable; Client resource safety unverified."
    if (steps.any { it.decision.contains("SchedulingPressure") }) {
        limitations += "Missed schedules can indicate generator pressure; Host saturation is not established."
    }
    val result = RpcSmartTestResult(settings, steps, maximum, stable?.throughputRps ?: 0.0,
        stable?.peakInFlight ?: 0, stop, search.boundaryObserved, stable != null, true,
        highestConfirmedTargetRps = stable?.targetRps ?: 0, limitations = limitations,
        confirmedWorkerLimit = stable?.concurrency ?: 0)
    return SmartRunOutput(result, attempts, correct, failures, missed, aggregate)
}

internal fun resourceSafetyFailure(settings: RpcSmartTestSettings, client: RpcDeviceTestResources?,
    host: RpcDeviceTestResources?): String? {
    val values = listOfNotNull(client, host)
    return when {
        values.any { it.thermalStopped } -> "ThermalSafetyStop"
        values.any { it.peakBatteryTemperatureMilliC?.let { temperature -> temperature >= 45_000 } == true } ->
            "BatteryTemperatureSafetyStop"
        values.any { it.peakMemoryBytes > settings.maximumMemoryBytes } -> "MemorySafetyBudgetReached"
        values.any { it.peakThreads > settings.maximumNativeThreads } -> "ThreadSafetyBudgetReached"
        else -> null
    }
}
