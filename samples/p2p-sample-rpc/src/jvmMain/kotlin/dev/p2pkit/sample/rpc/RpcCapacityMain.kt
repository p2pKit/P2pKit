package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.jvm
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.lang.management.ManagementFactory
import java.util.ServiceConfigurationError
import java.util.ServiceLoader
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicLongArray
import kotlin.system.exitProcess

private const val PERIOD_NANOS = 100_000_000L

/** Fixed-size, 1 ms buckets plus overflow. Reported percentile values are bucket upper bounds. */
internal class CapacityLatencyHistogram {
    private val buckets = AtomicLongArray(30_002)
    fun record(nanos: Long) {
        val positive = nanos.coerceAtLeast(0)
        val millis = (positive / 1_000_000 + if (positive % 1_000_000 == 0L) 0 else 1).coerceAtMost(30_001).toInt()
        buckets.incrementAndGet(millis)
    }
    fun percentile(percent: Int): Int {
        require(percent in 1..100)
        val total = (0 until buckets.length()).sumOf { buckets.get(it) }
        if (total == 0L) return -1
        val threshold = (total * percent + 99) / 100
        var seen = 0L
        for (index in 0 until buckets.length()) {
            seen += buckets.get(index)
            if (seen >= threshold) return index
        }
        error("Histogram accounting")
    }

    fun snapshot(): Map<String, Int> = linkedMapOf(
        "p50" to percentile(50), "p95" to percentile(95), "p99" to percentile(99), "max" to percentile(100),
    )
}

/** Sanitized machine-readable record. A mechanical pass never certifies resources, LAN or physical hosts. */
internal fun capacityResultJson(
    mode: String, mechanical: Boolean, numbers: Map<String, Long>, latency: CapacityLatencyHistogram,
    scheduling: CapacityLatencyHistogram? = null, failures: Map<String, Long> = emptyMap(),
): String = buildJsonObject {
    put("schema", 1)
    put("mode", mode)
    put("status", if (mechanical) "PENDING_RESOURCE_AND_NETWORK_REVIEW" else "FAIL")
    put("capacityQualified", false)
    put("measurements", JsonObject(numbers.mapValues { JsonPrimitive(it.value) }))
    val duration = numbers["actualSchedulingNanos"] ?: numbers["actualDurationNanos"]
    if (duration != null && duration > 0) {
        put("throughputResponsesPerSecond", (numbers["completed"] ?: 0L).toDouble() * 1_000_000_000 / duration)
    }
    put("latencyBucketUpperMs", JsonObject(latency.snapshot().mapValues { JsonPrimitive(it.value) }))
    put("latencyOverflowBucketMs", 30_001)
    scheduling?.let {
        put("schedulingDelayBucketUpperMs", JsonObject(it.snapshot().mapValues { entry -> JsonPrimitive(entry.value) }))
    }
    put("rpcFailuresByKind", JsonObject(failures.mapValues { JsonPrimitive(it.value) }))
    put("cleanup", "AWAIT_FINAL_RECORD")
}.toString()

private class Counters {
    val dispatched = AtomicLong()
    val completed = AtomicLong()
    val failed = AtomicLong()
    val missedDispatches = AtomicLong()
    val outstanding = AtomicLong()
    val disconnected = AtomicLong()
    val invalidHostSamples = AtomicLong()
    val hostSamples = AtomicLong()
    val infrastructure = AtomicLongArray(RpcFailureKind.entries.size)
    val latency = CapacityLatencyHistogram()
    val scheduling = CapacityLatencyHistogram()
}

/** Inspect at most two provider declarations before creating any application-owned resources. */
internal fun <T> instantiateSingleCapacityProvider(providers: Sequence<() -> T>): T = try {
    val choices = providers.take(2).toList()
    require(choices.size == 1) { "Exactly one reviewed local environment provider is required" }
    choices.single().invoke()
} catch (_: ServiceConfigurationError) {
    // ServiceLoader wraps constructor failures in Error rather than Exception. Do not leak a provider's
    // raw cause/stack trace (which may contain local configuration) through an uncaught JVM error.
    throw IllegalStateException("The reviewed local environment provider could not initialize")
}

/** This acknowledgement is necessary but not sufficient: execution still requires separate owner authorization. */
public fun main(args: Array<String>) {
    if (args.size != 2 || args[0] != "--owner-authorized-capacity-run" || args[1] !in setOf("--steady", "--large")) {
        System.err.println("Require separate owner authorization and: --owner-authorized-capacity-run --steady|--large")
        exitProcess(2)
    }
    try {
        val passedMechanicalChecks = runBlocking(Dispatchers.Default) {
            val providers = ServiceLoader.load(RpcCapacityEnvironment::class.java).stream()
            val environment = providers.use { stream ->
                instantiateSingleCapacityProvider(stream.iterator().asSequence().map { provider -> { provider.get() } })
            }
            runExperiment(environment, large = args[1] == "--large")
        }
        if (!passedMechanicalChecks) exitProcess(1)
    } catch (failure: RpcFailure) {
        System.err.println("ABORTED: RPC ${failure.kind.name}/${failure.phase.name}; qualification not established")
        exitProcess(1)
    } catch (_: Exception) {
        // No raw provider exception, endpoint, identity, secret, or payload in an exported transcript.
        System.err.println("ABORTED: local setup/measurement failed; qualification not established")
        exitProcess(1)
    }
}

private suspend fun runExperiment(environment: RpcCapacityEnvironment, large: Boolean): Boolean = supervisorScope {
    val clients = mutableListOf<RpcClient>()
    var cleanupSucceeded = true
    var measured = false
    try {
        val manifest = environment.manifest
        println("run=${manifest.runLabel},platform=${manifest.hostPlatform},source=${manifest.hostSourceSha}")
        println("hostArtifact=${manifest.hostArtifactSha256},driverArtifact=${manifest.driverArtifactSha256}")
        val count = if (large) 1 else RpcCapacityContract.CLIENTS
        repeat(count) { index ->
            val platform = RpcPlatform.jvm(environment.identityStore(index))
            val trust = environment.trustStore(index)
            clients += RpcClient.create(platform, this) {
                appId = RpcCapacityContract.appId
                lan = environment.lan
                trustStore = trust
            }
        }
        require(clients.map { it.fingerprint }.toSet().size == count) { "Independent identities are required" }
        // The existing two-pre-handshakes-per-source protection is NOT relaxed for synthetic clients.
        // Setup is outside the steady-state clock; established clients release those source leases.
        for (batch in clients.chunked(2)) {
            batch.map { client -> async { client.connect(environment.selectedHost) } }.awaitAll()
        }
        measured = if (large) runLarge(clients.single()) else runSteady(clients, environment)
    } finally {
        withContext(NonCancellable) {
            for (batch in clients.chunked(16)) {
                val results = batch.map { client -> async { runCatching { client.close() }.isSuccess } }.awaitAll()
                if (results.any { !it }) cleanupSucceeded = false
            }
            try { environment.close() } catch (_: Exception) { cleanupSucceeded = false }
        }
        if (!cleanupSucceeded) println("FAIL: retained cleanup was not verified")
        println("RPC_CAPACITY_FINAL_JSON:" + buildJsonObject {
            put("schema", 1)
            put("mechanicalChecksPassed", measured)
            put("cleanupVerified", cleanupSucceeded)
            put("capacityQualified", false)
        })
    }
    measured && cleanupSucceeded
}

private suspend fun runSteady(
    clients: List<RpcClient>, environment: RpcCapacityEnvironment,
): Boolean = supervisorScope {
    val counters = Counters()
    val permits = List(clients.size) { Semaphore(8) }
    val active = ConcurrentHashMap.newKeySet<Job>()
    val observers = clients.map { client ->
        launch {
            client.state.collect { if (it != RpcConnectionState.Ready) counters.disconnected.incrementAndGet() }
        }
    }
    val firstSample = withTimeout(5_000) {
        var sample = environment.sampleHost()
        while (sample.host.distinctAuthenticatedClients != RpcCapacityContract.CLIENTS) {
            delay(100)
            sample = environment.sampleHost()
        }
        sample
    }
    var previous = firstSample
    var maximumRss = firstSample.residentBytes
    var maximumThreads = firstSample.liveThreads
    var maximumQueued = firstSample.host.diagnostics.queuedCalls
    var maximumOutstanding = 0L
    fun recordHost(sample: RpcCapacityHostTelemetry) {
        counters.hostSamples.incrementAndGet()
        val stats = sample.host.diagnostics
        if (sample.host.distinctAuthenticatedClients != RpcCapacityContract.CLIENTS ||
            sample.uptimeMillis < previous.uptimeMillis || sample.processCpuNanos < previous.processCpuNanos ||
            stats.acceptedCalls < previous.host.diagnostics.acceptedCalls ||
            stats.completedCalls < previous.host.diagnostics.completedCalls
        ) counters.invalidHostSamples.incrementAndGet()
        previous = sample
        maximumRss = maxOf(maximumRss, sample.residentBytes)
        maximumThreads = maxOf(maximumThreads, sample.liveThreads)
        maximumQueued = maxOf(maximumQueued, stats.queuedCalls)
        maximumOutstanding = maxOf(maximumOutstanding, counters.outstanding.get())
        println(
            "host,${sample.uptimeMillis},${sample.processCpuNanos},${sample.residentBytes},${sample.liveThreads}," +
                "${stats.acceptedCalls},${stats.completedCalls},${stats.runningCalls},${stats.queuedCalls}," +
                "${stats.retainedPayloadBytes},${stats.retainedRecords},${sample.host.distinctAuthenticatedClients}",
        )
    }
    println("host,uptimeMs,cpuNs,rssBytes,threads,accepted,completed,running,queued,payloadBytes,records,connected")
    recordHost(firstSample)
    val sampler = launch {
        try {
            while (true) {
                delay(10_000)
                recordHost(withTimeout(5_000) { environment.sampleHost() })
                println(
                    "driver,heapBytes=${ManagementFactory.getMemoryMXBean().heapMemoryUsage.used}," +
                        "threads=${ManagementFactory.getThreadMXBean().threadCount}," +
                        "outstanding=${counters.outstanding.get()},completed=${counters.completed.get()}",
                )
            }
        } catch (cancelled: TimeoutCancellationException) {
            if (!currentCoroutineContext().isActive) throw cancelled
            counters.invalidHostSamples.incrementAndGet()
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (_: Exception) {
            counters.invalidHostSamples.incrementAndGet()
        }
    }
    try {
        val start = System.nanoTime()
        val ticks = RpcCapacityContract.STEADY_SECONDS * RpcCapacityContract.CALLS_PER_SECOND_PER_CLIENT
        repeat(ticks) { tick ->
            val scheduled = start + tick * PERIOD_NANOS
            val remaining = scheduled - System.nanoTime()
            if (remaining > 0) delay((remaining + 999_999) / 1_000_000)
            val dispatchDelay = System.nanoTime() - scheduled
            if (dispatchDelay >= PERIOD_NANOS) {
                counters.missedDispatches.addAndGet(clients.size.toLong())
                repeat(clients.size) { counters.scheduling.record(dispatchDelay) }
            } else clients.forEachIndexed { index, client ->
                if (!permits[index].tryAcquire()) {
                    // Never queue an unbounded backlog or throttle silently.
                    counters.missedDispatches.incrementAndGet()
                    counters.scheduling.record(System.nanoTime() - scheduled)
                } else {
                    counters.outstanding.incrementAndGet()
                    val job = launch(start = CoroutineStart.LAZY) {
                        val actualDelay = System.nanoTime() - scheduled
                        counters.scheduling.record(actualDelay)
                        if (actualDelay >= PERIOD_NANOS) {
                            counters.missedDispatches.incrementAndGet()
                        } else measureCall(client, counters)
                    }
                    active += job
                    job.invokeOnCompletion {
                        active -= job
                        counters.outstanding.decrementAndGet()
                        permits[index].release()
                    }
                    job.start()
                }
            }
        }
        // Finish the full 30-minute scheduling interval, then allow only the existing call deadline to drain.
        val end = start + RpcCapacityContract.STEADY_SECONDS * 1_000_000_000L
        val remaining = end - System.nanoTime()
        if (remaining > 0) delay((remaining + 999_999) / 1_000_000)
        val schedulingNanos = System.nanoTime() - start
        val drainStart = System.nanoTime()
        withTimeout(11_000) { while (active.isNotEmpty()) delay(10) }
        val drainNanos = System.nanoTime() - drainStart
        sampler.cancelAndJoin()
        recordHost(withTimeout(5_000) { environment.sampleHost() })
        val expected = clients.size.toLong() * ticks
        val before = firstSample.host.diagnostics
        val after = previous.host.diagnostics
        val mechanical = counters.dispatched.get() == expected && counters.completed.get() == expected &&
            counters.failed.get() == 0L && counters.missedDispatches.get() == 0L &&
            counters.disconnected.get() == 0L && counters.invalidHostSamples.get() == 0L &&
            counters.hostSamples.get() >= RpcCapacityContract.STEADY_SECONDS / 10 &&
            after.acceptedCalls - before.acceptedCalls == expected &&
            after.completedCalls - before.completedCalls == expected &&
            after.refusedCalls == before.refusedCalls && after.protocolFailures == before.protocolFailures &&
            after.connectionFailures == before.connectionFailures && after.runningCalls == 0 && after.queuedCalls == 0
        println(
            "expected=$expected,dispatched=${counters.dispatched.get()},completed=${counters.completed.get()}," +
                "failed=${counters.failed.get()},missed=${counters.missedDispatches.get()}," +
                "connectionChanges=${counters.disconnected.get()},invalidSamples=${counters.invalidHostSamples.get()}",
        )
        println("latencyBucketUpperMs,p50=${counters.latency.percentile(50)},p95=${counters.latency.percentile(95)}," +
            "p99=${counters.latency.percentile(99)},max=${counters.latency.percentile(100)}")
        for (kind in RpcFailureKind.entries) {
            if (counters.infrastructure.get(kind.ordinal) != 0L) {
                println("failureKind=${kind.name},count=${counters.infrastructure.get(kind.ordinal)}")
            }
        }
        println("RPC_CAPACITY_RESULT_JSON:" + capacityResultJson(
            "steady", mechanical, linkedMapOf(
                "clients" to clients.size.toLong(), "callsPerSecondPerClient" to 10L,
                "encodedRequestBytes" to 1024L, "encodedResponseBytes" to 1024L,
                "requiredDurationNanos" to RpcCapacityContract.STEADY_SECONDS * 1_000_000_000L,
                "actualSchedulingNanos" to schedulingNanos, "drainNanos" to drainNanos,
                "expected" to expected, "dispatched" to counters.dispatched.get(),
                "completed" to counters.completed.get(), "failed" to counters.failed.get(),
                "missedDispatches" to counters.missedDispatches.get(),
                "outstandingAfterDrain" to counters.outstanding.get(),
                "connectionChanges" to counters.disconnected.get(),
                "invalidHostSamples" to counters.invalidHostSamples.get(),
                "hostSamples" to counters.hostSamples.get(), "sampledMaxOutstanding" to maximumOutstanding,
                "sampledMaxHostRssBytes" to maximumRss, "sampledMaxHostThreads" to maximumThreads.toLong(),
                "sampledMaxHostQueue" to maximumQueued.toLong(),
                "hostUptimeDeltaMillis" to previous.uptimeMillis - firstSample.uptimeMillis,
                "hostCpuDeltaNanos" to previous.processCpuNanos - firstSample.processCpuNanos,
                "hostAcceptedDelta" to after.acceptedCalls - before.acceptedCalls,
                "hostCompletedDelta" to after.completedCalls - before.completedCalls,
            ), counters.latency, counters.scheduling,
            RpcFailureKind.entries.associate { it.name to counters.infrastructure.get(it.ordinal) },
        ))
        println(if (mechanical) "PENDING_HOST_RESOURCE_REVIEW_AND_PHYSICAL_INTEROPERABILITY" else "FAIL")
        // Exit 0 is measurement completion, NOT capacity qualification or release readiness.
        return@supervisorScope mechanical
    } finally {
        active.forEach { it.cancel() }
        sampler.cancelAndJoin()
        observers.forEach { it.cancelAndJoin() }
    }
}

private suspend fun measureCall(client: RpcClient, counters: Counters) {
    val begin = System.nanoTime()
    counters.dispatched.incrementAndGet()
    try {
        val reply = client.call(RpcCapacityContract.echo, RpcCapacityContract.payload)
        if (reply is RpcReply.Success && reply.value == RpcCapacityContract.payload) {
            counters.completed.incrementAndGet()
        } else counters.failed.incrementAndGet()
    } catch (cancelled: CancellationException) {
        counters.failed.incrementAndGet()
        throw cancelled
    } catch (failure: RpcFailure) {
        counters.infrastructure.incrementAndGet(failure.kind.ordinal)
        counters.failed.incrementAndGet()
    } catch (_: Exception) {
        counters.failed.incrementAndGet()
    } finally { counters.latency.record(System.nanoTime() - begin) }
}

private suspend fun runLarge(client: RpcClient): Boolean = supervisorScope {
    val payload = "a".repeat(RpcCapacityContract.MAXIMUM_BODY_BYTES - 2)
    val counters = Counters()
    val start = System.nanoTime()
    // Two concurrent calls, ten rounds; deliberately NOT the 1,280 calls/s steady-state experiment.
    repeat(10) {
        List(2) {
            async {
                val begin = System.nanoTime()
                counters.dispatched.incrementAndGet()
                try {
                    val reply = client.call(RpcCapacityContract.largeEcho, payload)
                    if (reply is RpcReply.Success && reply.value == payload) counters.completed.incrementAndGet()
                    else counters.failed.incrementAndGet()
                } catch (cancelled: CancellationException) {
                    counters.failed.incrementAndGet()
                    throw cancelled
                } catch (failure: RpcFailure) {
                    counters.infrastructure.incrementAndGet(failure.kind.ordinal)
                    counters.failed.incrementAndGet()
                } catch (_: Exception) {
                    counters.failed.incrementAndGet()
                } finally { counters.latency.record(System.nanoTime() - begin) }
            }
        }.awaitAll()
    }
    val passed = counters.completed.get() == 20L && counters.failed.get() == 0L
    println("RPC_CAPACITY_RESULT_JSON:" + capacityResultJson(
        "large", passed, linkedMapOf(
            "expected" to 20L, "concurrency" to 2L,
            "encodedRequestBytes" to RpcCapacityContract.MAXIMUM_BODY_BYTES.toLong(),
            "encodedResponseBytes" to RpcCapacityContract.MAXIMUM_BODY_BYTES.toLong(),
            "actualDurationNanos" to System.nanoTime() - start,
            "dispatched" to counters.dispatched.get(), "completed" to counters.completed.get(),
            "failed" to counters.failed.get(),
        ), counters.latency, failures = RpcFailureKind.entries.associate {
            it.name to counters.infrastructure.get(it.ordinal)
        },
    ))
    println(if (passed) "LARGE_BODY_MEASUREMENT_COMPLETE: 20 replies; platform qualification remains separate"
        else "FAIL")
    passed
}
