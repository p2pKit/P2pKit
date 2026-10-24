package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.jvm
import dev.p2pkit.sample.rpc.CapacityLatencyHistogram
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.RpcCapacityHostTelemetry
import dev.p2pkit.sample.rpc.awaitCapacityCompletions
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.util.concurrent.atomic.AtomicLong
import kotlin.system.exitProcess

/** The host publishes at 1Hz: a 5s driver delay alone can span only 4s of observed host samples. */
internal suspend fun awaitIoIdleTelemetry(
    start: RpcCapacityHostTelemetry,
    minimumMillis: Long = 5_000,
    sample: suspend () -> RpcCapacityHostTelemetry,
): RpcCapacityHostTelemetry {
    require(minimumMillis in 5_000..30_000)
    while (true) {
        val current = sample()
        check(current.uptimeMillis >= start.uptimeMillis && current.processCpuNanos >= start.processCpuNanos)
        check(current.host.diagnostics.completedCalls == start.host.diagnostics.completedCalls)
        if (current.uptimeMillis - start.uptimeMillis >= minimumMillis) return current
        delay(100)
    }
}

/** Production RPC + authenticated secure-v2 on an explicitly provisioned lab LAN; not physical qualification. */
@JvmName("main")
public fun runIoBenchmark(args: Array<String>) {
    require(args.size == 2 && args[0] == "--owner-authorized-io-benchmark")
    val seconds = args[1].toInt().also { require(it in 60..300) }
    var phase = "environment"
    try {
        runBlocking(Dispatchers.Default) { supervisorScope {
            val environment = LabEnvironment()
            val clients = mutableListOf<RpcClient>()
            val latency = CapacityLatencyHistogram()
            val completed = AtomicLong()
            val lateSlots = AtomicLong()
            var measurements: Map<String, Long>? = null
            try {
                val before = environment.sampleHost()
                phase = "identities"
                repeat(environment.clientCount) { index ->
                    val trust = environment.trustStore(index)
                    clients += RpcClient.create(RpcPlatform.jvm(environment.identityStore(index)), this) {
                        appId = RpcCapacityContract.appId
                        lan = environment.lan
                        trustStore = trust
                    }
                }
                check(clients.map { it.fingerprint }.toSet().size == environment.clientCount)
                phase = "authenticated-connect"
                withTimeout(180_000) {
                    // Preserve per-source pre-handshake admission. Never increase it to create the load faster.
                    clients.chunked(2).forEach { batch ->
                        batch.map { async { it.connect(environment.selectedHost) } }.awaitAll()
                    }
                }
                suspend fun healthySample(): RpcCapacityHostTelemetry = environment.sampleHost().also {
                    check(it.host.distinctAuthenticatedClients == clients.size)
                    check(clients.all { client -> client.state.value == RpcConnectionState.Ready })
                    check(it.host.diagnostics.connectionFailures == 0L && it.host.diagnostics.protocolFailures == 0L)
                }
                phase = "warmup"
                repeat(4) {
                    clients.map { client -> async {
                        check(client.call(RpcCapacityContract.echo, RpcCapacityContract.payload) ==
                            RpcReply.Success(RpcCapacityContract.payload))
                    } }.awaitAll()
                }
                delay(3_000)
                val idleStart = healthySample()
                phase = "idle"
                delay(5_000)
                val idleEnd = withTimeout(5_000) { awaitIoIdleTelemetry(idleStart, sample = ::healthySample) }
                check(idleEnd.host.diagnostics.completedCalls == idleStart.host.diagnostics.completedCalls)
                // Keep the original cold/early idle observation, then measure three complete
                // 10-second keepalive intervals separately after another 10 seconds of settling.
                // Do not mistake startup JIT/GC, or one synchronized heartbeat burst, for steady idle.
                phase = "steady-idle"
                delay(10_000)
                val steadyStart = healthySample()
                delay(30_000)
                val steadyEnd = withTimeout(5_000) { awaitIoIdleTelemetry(steadyStart, 30_000, ::healthySample) }
                phase = "workload"
                val start = System.nanoTime() + 200_000_000
                withTimeout((seconds + 30L) * 1_000) {
                    clients.mapIndexed { index, client -> async {
                        repeat(seconds * 10) { tick ->
                            val scheduled = start + tick * 100_000_000L + index * 100_000_000L / clients.size
                            val remaining = scheduled - System.nanoTime()
                            if (remaining > 0) delay((remaining + 999_999) / 1_000_000)
                            val sent = System.nanoTime()
                            if (sent - scheduled >= 100_000_000) lateSlots.incrementAndGet()
                            check(client.call(RpcCapacityContract.echo, RpcCapacityContract.payload) ==
                                RpcReply.Success(RpcCapacityContract.payload))
                            latency.record(System.nanoTime() - sent)
                            completed.incrementAndGet()
                        }
                    } }.awaitAll()
                }
                val duration = System.nanoTime() - start
                val expected = clients.size.toLong() * seconds * 10
                val after = withTimeout(5_000) {
                    awaitCapacityCompletions(idleEnd.host.diagnostics.completedCalls + expected, ::healthySample)
                }
                check(completed.get() == expected)
                check(after.host.diagnostics.completedCalls - idleEnd.host.diagnostics.completedCalls == expected)
                check(after.host.diagnostics.refusedCalls == 0L && after.host.diagnostics.duplicateRequests == 0L)
                measurements = mapOf(
                    "clients" to clients.size.toLong(), "seconds" to seconds.toLong(), "responses" to completed.get(),
                    "activeWallNs" to duration, "late100msSlots" to lateSlots.get(),
                    "hostThreadsBeforeConnections" to before.liveThreads.toLong(),
                    "hostThreadsIdle" to idleEnd.liveThreads.toLong(), "hostThreadsAfter" to after.liveThreads.toLong(),
                    "hostRssBeforeBytes" to before.residentBytes, "hostRssIdleBytes" to idleEnd.residentBytes,
                    "hostRssAfterBytes" to after.residentBytes,
                    "hostIdleWallMs" to idleEnd.uptimeMillis - idleStart.uptimeMillis,
                    "hostIdleCpuNs" to idleEnd.processCpuNanos - idleStart.processCpuNanos,
                    "hostSteadyIdleStartMs" to steadyStart.uptimeMillis,
                    "hostSteadyIdleWallMs" to steadyEnd.uptimeMillis - steadyStart.uptimeMillis,
                    "hostSteadyIdleCpuNs" to steadyEnd.processCpuNanos - steadyStart.processCpuNanos,
                    "hostSteadyIdleThreads" to steadyEnd.liveThreads.toLong(),
                    "hostSteadyIdleRssBytes" to steadyEnd.residentBytes,
                    "hostActiveCpuNs" to after.processCpuNanos - steadyEnd.processCpuNanos,
                    "hostActiveWallMs" to after.uptimeMillis - steadyEnd.uptimeMillis,
                    "hostRetainedRecords" to after.host.diagnostics.retainedRecords.toLong(),
                    "hostPayloadBytes" to after.host.diagnostics.retainedPayloadBytes,
                )
            } finally {
                withContext(NonCancellable) {
                    // Preserve the failing workload phase. Cleanup failure is never a successful
                    // benchmark and must not prevent retirement of the other original owners.
                    var cleanupFailure: Throwable? = null
                    clients.chunked(16).forEach { batch ->
                        batch.map { client -> async { runCatching { client.close() }.exceptionOrNull() } }
                            .awaitAll().filterNotNull().forEach { error ->
                                if (cleanupFailure == null) cleanupFailure = error
                                else cleanupFailure.addSuppressed(error)
                            }
                    }
                    try { environment.close() } catch (error: Throwable) {
                        if (cleanupFailure == null) cleanupFailure = error else cleanupFailure.addSuppressed(error)
                    }
                    cleanupFailure?.let {
                        phase += "/cleanup-failed"
                        throw it
                    }
                }
            }
            println("RPC_IO_BENCHMARK_JSON:" + buildJsonObject {
                put("schema", 2)
                put("source", environment.manifest.hostSourceSha)
                put("hostArtifact", environment.manifest.hostArtifactSha256)
                put("driverArtifact", environment.manifest.driverArtifactSha256)
                put("scope", "AUTHENTICATED_RPC_LAB_NOT_PHYSICAL_OR_MOBILE_QUALIFICATION")
                put("cleanup", true)
                put("measurements", JsonObject(checkNotNull(measurements).mapValues { JsonPrimitive(it.value) }))
                put("latencyUpperMs", JsonObject(latency.snapshot().mapValues { JsonPrimitive(it.value) }))
            })
        } }
    } catch (failure: Exception) {
        val type = if (failure is RpcFailure) "${failure.kind}/${failure.phase}" else failure.javaClass.simpleName
        System.err.println("RPC_IO_BENCHMARK_FAILED phase=$phase type=$type; not qualified")
        val frames = failure.stackTrace.filter { it.className.startsWith("dev.p2pkit.") }.take(8)
        System.err.println("RPC_IO_FAILURE_FRAMES:" + frames.joinToString(";") {
            "${it.className}.${it.methodName}:${it.lineNumber}"
        }) // Source-owned locations only; exception messages/payloads stay private.
        exitProcess(1)
    }
}
