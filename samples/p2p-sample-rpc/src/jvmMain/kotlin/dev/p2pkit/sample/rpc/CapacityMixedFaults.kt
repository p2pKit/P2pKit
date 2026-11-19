package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcReply
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlin.time.Duration.Companion.seconds

internal const val MIXED_FAULT_EPOCHS = 60
internal const val MIXED_FAULT_EPOCH_MILLIS = 30_000L

internal suspend fun runCapacityMixedFaults(
    peers: List<CapacityControlPeer>, sampleHost: suspend () -> RpcCapacityHostSnapshot,
    nowNanos: () -> Long = System::nanoTime,
): JsonObject = supervisorScope {
    capacityProfileLimits(peers.size)
    val attemptedAt = nowNanos()
    var measuringFrom: Long? = null
    val counters = linkedMapOf(
        "roundsCompleted" to 0L, "liveEchoes" to 0L, "cohortEchoes" to 0L,
        "sentDeadlines" to 0L, "sentCancellations" to 0L, "disconnectUnknownOutcomes" to 0L,
        "authorizationRefusals" to 0L, "businessErrors" to 0L,
        "disconnects" to 0L, "reconnects" to 0L, "retiredHandlers" to 0L,
    )
    fun increment(key: String) { counters[key] = counters.getValue(key) + 1 }
    val observer = peers.last()
    var phase = "initial-cohort"
    var passed = false

    suspend fun fullCohort() = withTimeout(5_000) {
        while (true) {
            val sample = sampleHost()
            if (peers.all { it.state == RpcConnectionState.Ready } &&
                sample.distinctAuthenticatedClients == peers.size &&
                sample.diagnostics.runningCalls == 0 && sample.diagnostics.queuedCalls == 0
            ) return@withTimeout
            delay(20)
        }
    }

    suspend fun hostState(): CapacityExerciseCounters {
        val reply = observer.call(RpcCapacityExercises.state, "", 2.seconds)
        check(reply is RpcReply.Success)
        val fields = reply.value.split(',')
        check(fields.size == 5 && fields.all { it.matches(Regex("0|[1-9][0-9]{0,18}")) })
        val values = fields.map(String::toLong)
        return CapacityExerciseCounters(values[0], values[1], values[2], values[3], values[4])
    }

    suspend fun awaitState(entered: Long, retired: Long, timeoutMillis: Long = 2_000) =
        withTimeout(timeoutMillis) {
            val expected = CapacityExerciseCounters(holdEntered = entered, holdRetired = retired)
            while (hostState() != expected) delay(20)
        }

    fun expectFailure(
        failure: Throwable?, kind: RpcFailureKind, evidence: RpcExecutionEvidence,
    ) {
        check(failure is RpcFailure && failure.kind == kind && failure.phase == RpcFailurePhase.AwaitingResponse &&
            failure.requestId != null && failure.executionEvidence == evidence)
    }

    suspend fun echo(peer: CapacityControlPeer, value: String) {
        check(peer.call(RpcCapacityExercises.echo, value, 2.seconds) == RpcReply.Success(value))
    }

    try {
        fullCohort()
        check(hostState() == CapacityExerciseCounters())
        val started = nowNanos()
        measuringFrom = started
        repeat(MIXED_FAULT_EPOCHS) { round ->
            // Three original identities rotate as fault subjects. A different peer verifies live traffic
            // while remote handlers are held, then every member of the original cohort replies.
            val baseline = round * 3L
            val deadlinePeer = peers[round * 3 % (peers.size - 1)]
            val cancelPeer = peers[(round * 3 + 1) % (peers.size - 1)]
            val lostPeer = peers[(round * 3 + 2) % (peers.size - 1)]
            val boundary = started + (round + 1) * MIXED_FAULT_EPOCH_MILLIS * 1_000_000
            withTimeout(MIXED_FAULT_EPOCH_MILLIS) {
                supervisorScope {
                    phase = "remote-entry"
                    val cancelled = async { cancelPeer.call(RpcCapacityExercises.hold, "cancel") }
                    awaitState(baseline + 1, baseline)
                    val lost = async {
                        runCatching { lostPeer.call(RpcCapacityExercises.hold, "disconnect") }.exceptionOrNull()
                    }
                    awaitState(baseline + 2, baseline)
                    val deadline = async {
                        runCatching { deadlinePeer.call(RpcCapacityExercises.hold, "deadline", 3.seconds) }
                            .exceptionOrNull()
                    }
                    awaitState(baseline + 3, baseline)

                    phase = "healthy-traffic-and-refusals"
                    echo(observer, "live-$round")
                    increment("liveEchoes")
                    check(observer.call(RpcCapacityExercises.reject, "") == RpcReply.ApplicationError("synthetic"))
                    increment("businessErrors")
                    expectFailure(runCatching { observer.call(RpcCapacityExercises.denied, "") }.exceptionOrNull(),
                        RpcFailureKind.Unauthorized, RpcExecutionEvidence.RejectedBeforeExecution)
                    increment("authorizationRefusals")

                    phase = "fault-outcomes"
                    check(cancelled.isActive)
                    cancelled.cancelAndJoin()
                    check(runCatching { cancelled.await() }.exceptionOrNull() is CancellationException)
                    increment("sentCancellations")
                    lostPeer.disconnect()
                    increment("disconnects")
                    expectFailure(lost.await(), RpcFailureKind.UnknownOutcome, RpcExecutionEvidence.MayHaveExecuted)
                    increment("disconnectUnknownOutcomes")
                    expectFailure(deadline.await(), RpcFailureKind.DeadlineExceeded,
                        RpcExecutionEvidence.MayHaveExecuted)
                    increment("sentDeadlines")
                    awaitState(baseline + 3, baseline + 3, 12_000)
                    counters["retiredHandlers"] = baseline + 3
                    lostPeer.reconnect()
                    increment("reconnects")
                }

                phase = "original-cohort-recovery"
                for ((batchIndex, batch) in peers.chunked(16).withIndex()) {
                    batch.mapIndexed { index, peer ->
                        async { echo(peer, "round-$round-$batchIndex-$index") }
                    }.awaitAll()
                    counters["cohortEchoes"] = counters.getValue("cohortEchoes") + batch.size
                }
                fullCohort()
            }
            phase = "epoch-schedule"
            val remaining = boundary - nowNanos()
            check(remaining > 0) { "No catch-up after a missed epoch" }
            increment("roundsCompleted")
            delay((remaining + 999_999) / 1_000_000)
        }
        passed = true
    } catch (failure: CancellationException) {
        if (!currentCoroutineContext().isActive) throw failure
    } catch (_: Exception) {
        // The report keeps the exact finite phase and partial counters. The launcher still fails.
    }
    buildJsonObject {
        put("schema", 2)
        put("clientCount", peers.size)
        put("mode", "mixed-fault")
        put("scope", "AUTHENTICATED_MIXED_FAULTS_NOT_STEADY")
        put("status", if (passed) "PENDING_RESOURCE_AND_NETWORK_REVIEW" else "FAIL")
        put("capacityQualified", false)
        put("failureCase", if (passed) JsonNull else JsonPrimitive(phase))
        put("cleanup", "AWAIT_FINAL_RECORD")
        put("measurements", JsonObject((counters + ("elapsedNanos" to nowNanos() - (measuringFrom ?: attemptedAt)))
            .mapValues { JsonPrimitive(it.value) }))
    }
}
