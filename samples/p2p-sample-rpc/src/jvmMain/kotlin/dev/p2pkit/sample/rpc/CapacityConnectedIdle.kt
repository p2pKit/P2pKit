package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcConnectionState
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.util.concurrent.atomic.AtomicLong

internal const val CAPACITY_IDLE_SETTLE_MILLIS = 10_000L
internal const val CAPACITY_IDLE_REQUIRED_MILLIS = 30_000L
internal const val CAPACITY_IDLE_SAMPLE_PERIOD_MILLIS = 5_000L
internal const val CAPACITY_IDLE_TIMEOUT_MILLIS = 55_000L
private const val MAXIMUM_IDLE_SAMPLES = 10

internal class CapacityConnectedIdleOutcome(
    val clientCount: Int, val mechanical: Boolean, val failureStage: String?,
    val measurements: Map<String, Long>, val samples: List<Map<String, Long>>,
) {
    fun json(manifest: RpcCapacityManifest): String = buildJsonObject {
        put("schema", 2)
        put("clientCount", clientCount)
        put("sourceSha", manifest.hostSourceSha)
        put("runLabel", manifest.runLabel)
        put("hostPlatform", manifest.hostPlatform.name)
        put("hostArtifactSha256", manifest.hostArtifactSha256)
        put("driverArtifactSha256", manifest.driverArtifactSha256)
        put("scope", "CONNECTED_IDLE_RESOURCE_OBSERVATION_NOT_CAPACITY")
        put("status", if (mechanical) "OBSERVED_CONNECTED_IDLE_NOT_CAPACITY" else "FAIL")
        put("capacityQualified", false)
        put("settleMillis", CAPACITY_IDLE_SETTLE_MILLIS)
        put("requiredHostIdleMillis", CAPACITY_IDLE_REQUIRED_MILLIS)
        put("failureStage", failureStage?.let(::JsonPrimitive) ?: JsonNull)
        put("measurements", JsonObject(measurements.mapValues { JsonPrimitive(it.value) }))
        put("samples", buildJsonArray {
            samples.forEach { sample -> add(JsonObject(sample.mapValues { JsonPrimitive(it.value) })) }
        })
    }.toString()
}

/**
 * Real connected idle, not an empty-process baseline or a deduction from the steady workload.
 * State collectors run throughout observation; sampled host counters must show no intervening RPC work.
 * CPU, RSS and native-thread values come from the real host provider, never from the generator JVM.
 */
internal suspend fun observeCapacityConnectedIdle(
    states: List<StateFlow<RpcConnectionState>>, sampleHost: suspend () -> RpcCapacityHostTelemetry,
    driverCpuNanos: () -> Long, nowNanos: () -> Long = System::nanoTime,
): CapacityConnectedIdleOutcome = supervisorScope {
    val clientCount = states.size
    val limits = capacityProfileLimits(clientCount)
    val observerScope = this
    val observers = mutableListOf<Job>()
    val changes = AtomicLong()
    val samples = mutableListOf<Map<String, Long>>()
    val started = nowNanos()
    var settledNanos = 0L
    var observationStarted = 0L
    var invalidSamples = 0L
    var phase = "settle"
    var mechanical = false

    fun record(host: RpcCapacityHostTelemetry): Boolean {
        val driverNow = nowNanos()
        if (samples.isEmpty()) observationStarted = driverNow
        val stats = host.host.diagnostics
        val row = linkedMapOf(
            "uptimeMillis" to host.uptimeMillis, "cpuNanos" to host.processCpuNanos,
            "residentBytes" to host.residentBytes, "nativeThreads" to host.liveThreads.toLong(),
            "connected" to host.host.distinctAuthenticatedClients.toLong(),
            "accepted" to stats.acceptedCalls, "completed" to stats.completedCalls,
            "refused" to stats.refusedCalls, "duplicates" to stats.duplicateRequests,
            "droppedNotifications" to stats.droppedNotifications, "protocolFailures" to stats.protocolFailures,
            "connectionFailures" to stats.connectionFailures, "running" to stats.runningCalls.toLong(),
            "queued" to stats.queuedCalls.toLong(), "records" to stats.retainedRecords.toLong(),
            "payloadBytes" to stats.retainedPayloadBytes,
            "driverElapsedNanos" to driverNow - observationStarted, "driverCpuNanos" to driverCpuNanos(),
        )
        val previous = samples.lastOrNull()
        samples += row
        val valid = row.values.all { it >= 0 } && row.getValue("residentBytes") > 0 &&
            row.getValue("nativeThreads") > 0 && row.getValue("connected") == clientCount.toLong() &&
            stats.runningCalls == 0 && stats.queuedCalls == 0 && stats.acceptedCalls == stats.completedCalls &&
            stats.retainedRecords <= limits.totalRecords && stats.retainedPayloadBytes <= limits.payloadBytes &&
            states.all { it.value == RpcConnectionState.Ready } && changes.get() == 0L &&
            (previous == null || (
                row.getValue("uptimeMillis") > previous.getValue("uptimeMillis") &&
                    row.getValue("cpuNanos") >= previous.getValue("cpuNanos") &&
                    row.getValue("driverElapsedNanos") >= previous.getValue("driverElapsedNanos") +
                    CAPACITY_IDLE_SAMPLE_PERIOD_MILLIS * 1_000_000 &&
                    row.getValue("driverCpuNanos") >= previous.getValue("driverCpuNanos") &&
                    IDLE_UNCHANGED_COUNTERS.all { row.getValue(it) == previous.getValue(it) }
                ))
        if (!valid) invalidSamples++
        return valid
    }

    try {
        withTimeout(CAPACITY_IDLE_TIMEOUT_MILLIS) {
            delay(CAPACITY_IDLE_SETTLE_MILLIS)
            settledNanos = nowNanos() - started
            // Register synchronously before the baseline read; no per-client thread or polling loop.
            states.forEach { state ->
                observers += observerScope.launch(start = CoroutineStart.UNDISPATCHED) {
                    state.collect { if (it != RpcConnectionState.Ready) changes.incrementAndGet() }
                }
            }
            phase = "baseline"
            check(record(withTimeout(5_000) { sampleHost() }))
            phase = "observe"
            val firstUptime = samples.first().getValue("uptimeMillis")
            while (samples.last().getValue("uptimeMillis") - firstUptime < CAPACITY_IDLE_REQUIRED_MILLIS ||
                samples.last().getValue("driverElapsedNanos") < CAPACITY_IDLE_REQUIRED_MILLIS * 1_000_000) {
                check(samples.size < MAXIMUM_IDLE_SAMPLES)
                delay(CAPACITY_IDLE_SAMPLE_PERIOD_MILLIS)
                check(record(withTimeout(5_000) { sampleHost() }))
            }
            phase = "validation"
            check(changes.get() == 0L && invalidSamples == 0L && states.all { it.value == RpcConnectionState.Ready })
            // Both clocks must cover 30 seconds. Cached telemetry may add, never subtract, observation time.
            val hostMillis = samples.last().getValue("uptimeMillis") - firstUptime
            val driverMillis = samples.last().getValue("driverElapsedNanos") / 1_000_000
            check(hostMillis in (driverMillis - 5_000)..(driverMillis + 5_000))
            mechanical = true
        }
    } catch (cancelled: TimeoutCancellationException) {
        // This bounded observation can fail independently. An outer invocation cancellation still propagates.
        if (!currentCoroutineContext().isActive) throw cancelled
    } catch (cancelled: CancellationException) {
        throw cancelled
    } catch (_: Exception) {
        // Only fixed stage labels and numeric samples are exported, never a provider's raw exception.
    } finally {
        withContext(NonCancellable) { observers.forEach { it.cancelAndJoin() } }
    }
    if (changes.get() != 0L) mechanical = false
    val first = samples.firstOrNull()
    val last = samples.lastOrNull()
    fun finalValue(name: String): Long = last?.getValue(name) ?: 0L
    fun firstValue(name: String): Long = first?.getValue(name) ?: 0L
    fun minimum(name: String): Long = samples.minOfOrNull { it.getValue(name) } ?: 0L
    fun maximum(name: String): Long = samples.maxOfOrNull { it.getValue(name) } ?: 0L
    CapacityConnectedIdleOutcome(clientCount, mechanical, if (mechanical) null else phase, linkedMapOf(
        "clients" to clientCount.toLong(), "sampleCount" to samples.size.toLong(),
        "actualDurationNanos" to nowNanos() - started, "actualSettleNanos" to settledNanos,
        "hostUptimeDeltaMillis" to finalValue("uptimeMillis") - firstValue("uptimeMillis"),
        "hostCpuDeltaNanos" to finalValue("cpuNanos") - firstValue("cpuNanos"),
        "driverElapsedNanos" to finalValue("driverElapsedNanos"),
        "driverCpuDeltaNanos" to finalValue("driverCpuNanos") - firstValue("driverCpuNanos"),
        "connectionChanges" to changes.get(), "invalidHostSamples" to invalidSamples,
        "sampledMinHostRssBytes" to minimum("residentBytes"), "sampledMaxHostRssBytes" to maximum("residentBytes"),
        "sampledMinHostThreads" to minimum("nativeThreads"), "sampledMaxHostThreads" to maximum("nativeThreads"),
        "hostConnectionsBefore" to firstValue("connected"), "hostConnectionsAfter" to finalValue("connected"),
        "hostAcceptedDelta" to finalValue("accepted") - firstValue("accepted"),
        "hostCompletedDelta" to finalValue("completed") - firstValue("completed"),
        "hostRunningAfter" to finalValue("running"), "hostQueuedAfter" to finalValue("queued"),
    ), samples.map { it.toMap() })
}

private val IDLE_UNCHANGED_COUNTERS = listOf(
    "accepted", "completed", "refused", "duplicates", "droppedNotifications", "protocolFailures", "connectionFailures",
)
