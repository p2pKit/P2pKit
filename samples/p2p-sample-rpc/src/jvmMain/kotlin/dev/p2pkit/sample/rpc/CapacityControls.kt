package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcSelectedHost
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
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
import kotlin.time.Duration
import kotlin.time.Duration.Companion.seconds

internal val CAPACITY_CORRECTNESS_CASES = listOf(
    "full-authenticated-cohort", "concurrent-correlation", "application-error", "procedure-authorization",
    "sent-deadline", "sent-cancellation", "slow-handler-fairness", "disconnect-during-call",
    "full-authenticated-cohort-after",
)
internal val CAPACITY_CHURN_CASES = listOf(
    "full-authenticated-cohort", "five-round-original-identity-reconnect", "full-authenticated-cohort-after",
)
internal const val CAPACITY_CHURN_ROUNDS = 5
internal const val CAPACITY_SLOW_HANDLER_CLIENTS = 16
internal val CAPACITY_CONTROL_FIELDS = listOf(
    "clients", "expectedEchoResponses", "echoResponses", "concurrentEchoResponses", "applicationErrors",
    "authorizationRefusals", "sentDeadlineFailures", "sentCancellations", "disconnectUnknownOutcomes",
    "holdEntered", "holdRetired", "slowHandlerResponses", "fairnessEchoResponses", "churnRounds",
    "disconnects", "reconnects", "actualDurationNanos", "hostConnectionsBefore", "hostConnectionsAfter",
    "hostRunningAfter", "hostQueuedAfter",
)

/** Test seam around the actual client facade; production still uses its ordinary secure LAN transport. */
internal interface CapacityControlPeer {
    val state: RpcConnectionState
    suspend fun call(
        procedure: RpcProcedure<String, String, String>, value: String, timeout: Duration = 10.seconds,
    ): RpcReply<String, String>
    suspend fun disconnect()
    suspend fun reconnect()
}

private class ActualCapacityControlPeer(
    private val client: RpcClient, private val selected: RpcSelectedHost,
) : CapacityControlPeer {
    override val state: RpcConnectionState get() = client.state.value
    override suspend fun call(
        procedure: RpcProcedure<String, String, String>, value: String, timeout: Duration,
    ): RpcReply<String, String> = client.call(procedure, value, timeout)
    override suspend fun disconnect() { client.disconnect() }
    override suspend fun reconnect() { client.connect(selected) }
}

internal class CapacityControlOutcome(
    val mode: String, val clientCount: Int, val mechanical: Boolean,
    val passedCases: List<String>, val failureCase: String?, val measurements: Map<String, Long>,
) {
    fun json(): String = buildJsonObject {
        put("schema", 2)
        put("clientCount", clientCount)
        put("mode", mode)
        put("scope", "REAL_AUTHENTICATED_RPC_CONTROLS_NOT_CAPACITY")
        put("status", if (mechanical) "PENDING_RESOURCE_AND_NETWORK_REVIEW" else "FAIL")
        put("capacityQualified", false)
        put("expectedCases", buildJsonArray { cases(mode).forEach { add(it) } })
        put("passedCases", buildJsonArray { passedCases.forEach { add(it) } })
        put("failureCase", failureCase?.let(::JsonPrimitive) ?: JsonNull)
        put("measurements", JsonObject(measurements.mapValues { JsonPrimitive(it.value) }))
        // A sleeping handler checks host fairness. It is not a peer refusing to consume socket bytes.
        put("trueSlowConsumerQualified", false)
        put("cleanup", "AWAIT_FINAL_RECORD")
    }.toString()
}

private fun cases(mode: String): List<String> = when (mode) {
    "correctness" -> CAPACITY_CORRECTNESS_CASES
    "churn" -> CAPACITY_CHURN_CASES
    else -> throw IllegalArgumentException("Unknown capacity control mode")
}

internal suspend fun runCapacityControls(
    mode: String, clients: List<RpcClient>, environment: RpcCapacityEnvironment,
): Boolean {
    require(environment.schemaVersion == 2 && clients.size == environment.clientCount)
    val outcome = runCapacityControlProgram(mode,
        clients.map { ActualCapacityControlPeer(it, environment.selectedHost) },
        sampleHost = { environment.sampleHost().host })
    println("RPC_CAPACITY_RESULT_JSON:" + outcome.json())
    return outcome.mechanical
}

/** Fully accounted finite controls, run separately from the unchanged30-minute steady-state clocks. */
internal suspend fun runCapacityControlProgram(
    mode: String, peers: List<CapacityControlPeer>, sampleHost: suspend () -> RpcCapacityHostSnapshot,
    nowNanos: () -> Long = System::nanoTime,
): CapacityControlOutcome = supervisorScope {
    capacityProfileLimits(peers.size)
    val expectedCases = cases(mode)
    val passed = mutableListOf<String>()
    val active = mutableListOf<Job>()
    val metrics = CAPACITY_CONTROL_FIELDS.associateWith { AtomicLong() }
    fun add(name: String, count: Long = 1) { metrics.getValue(name).addAndGet(count) }
    fun set(name: String, count: Long) { metrics.getValue(name).set(count) }
    set("clients", peers.size.toLong())
    set("expectedEchoResponses", if (mode == "correctness") peers.size * 3L + 5 else
        peers.size.toLong() * CAPACITY_CHURN_ROUNDS)
    val started = nowNanos()
    var phase = expectedCases.first()
    var mechanical = false
    val observer = peers.last()

    suspend fun echo(peer: CapacityControlPeer, value: String = "synthetic-live") {
        check(peer.call(RpcCapacityExercises.echo, value) == RpcReply.Success(value))
        add("echoResponses")
    }

    suspend fun state(): CapacityExerciseCounters {
        val reply = observer.call(RpcCapacityExercises.state, "", timeout = 2.seconds)
        check(reply is RpcReply.Success)
        val parts = reply.value.split(',')
        check(parts.size == 5 && parts.all { it.matches(Regex("0|[1-9][0-9]{0,18}")) })
        val values = parts.map(String::toLong)
        check(values.all { it >= 0 } && values[1] <= values[0] && values[3] <= values[2] && values[4] == 0L)
        set("holdEntered", values[0])
        set("holdRetired", values[1])
        return CapacityExerciseCounters(values[0], values[1], values[2], values[3], values[4])
    }

    suspend fun awaitState(expected: CapacityExerciseCounters, boundMillis: Long = 2_000) =
        withTimeout(boundMillis) {
            while (state() != expected) delay(20)
        }

    suspend fun fullCohort(): RpcCapacityHostSnapshot = withTimeout(5_000) {
        var host = sampleHost()
        while (host.distinctAuthenticatedClients != peers.size || host.diagnostics.runningCalls != 0 ||
            host.diagnostics.queuedCalls != 0 || peers.any { it.state != RpcConnectionState.Ready }) {
            delay(20)
            host = sampleHost()
        }
        host
    }

    try {
        withTimeout(if (mode == "correctness") 90_000 else 300_000) {
            val before = fullCohort()
            set("hostConnectionsBefore", before.distinctAuthenticatedClients.toLong())
            passed += phase
            if (mode == "correctness") {
                check(state() == CapacityExerciseCounters())
                phase = expectedCases[1]
                for (batch in peers.withIndex().toList().chunked(16)) {
                    batch.flatMap { (index, peer) -> List(2) { round ->
                        async {
                            echo(peer, "correlation-$index-$round-" + "\u03a9\n\"\\".repeat(10))
                            add("concurrentEchoResponses")
                        }.also { active += it }
                    } }.awaitAll()
                }
                passed += phase

                phase = expectedCases[2]
                check(peers.first().call(RpcCapacityExercises.reject, "") == RpcReply.ApplicationError("synthetic"))
                add("applicationErrors")
                passed += phase

                phase = expectedCases[3]
                val denied = runCatching { peers.first().call(RpcCapacityExercises.denied, "") }.exceptionOrNull()
                check(denied is RpcFailure && denied.kind == RpcFailureKind.Unauthorized &&
                    denied.phase == RpcFailurePhase.AwaitingResponse &&
                    denied.executionEvidence == RpcExecutionEvidence.RejectedBeforeExecution &&
                    denied.requestId != null)
                check(state() == CapacityExerciseCounters())
                add("authorizationRefusals")
                passed += phase

                phase = expectedCases[4]
                val deadline = async {
                    runCatching { peers.first().call(RpcCapacityExercises.hold, "deadline", timeout = 3.seconds) }
                }.also { active += it }
                awaitState(CapacityExerciseCounters(holdEntered = 1))
                val deadlineFailure = deadline.await().exceptionOrNull()
                check(deadlineFailure is RpcFailure && deadlineFailure.kind == RpcFailureKind.DeadlineExceeded &&
                    deadlineFailure.phase == RpcFailurePhase.AwaitingResponse && deadlineFailure.requestId != null &&
                    deadlineFailure.executionEvidence == RpcExecutionEvidence.MayHaveExecuted)
                awaitState(CapacityExerciseCounters(holdEntered = 1, holdRetired = 1))
                add("sentDeadlineFailures")
                echo(observer)
                passed += phase

                phase = expectedCases[5]
                val cancelled = async { peers.first().call(RpcCapacityExercises.hold, "cancel") }
                    .also { active += it }
                awaitState(CapacityExerciseCounters(holdEntered = 2, holdRetired = 1))
                cancelled.cancelAndJoin()
                check(cancelled.isCancelled)
                awaitState(CapacityExerciseCounters(holdEntered = 2, holdRetired = 2))
                add("sentCancellations")
                echo(observer)
                passed += phase

                phase = expectedCases[6]
                val slow = peers.take(CAPACITY_SLOW_HANDLER_CLIENTS).map { peer ->
                    async {
                        check(peer.call(RpcCapacityExercises.slow, "synthetic-slow") ==
                            RpcReply.Success("synthetic-slow"))
                        add("slowHandlerResponses")
                    }.also { active += it }
                }
                awaitState(CapacityExerciseCounters(2, 2, CAPACITY_SLOW_HANDLER_CLIENTS.toLong()))
                withTimeout(2_000) { echo(observer) }
                add("fairnessEchoResponses")
                slow.awaitAll()
                awaitState(CapacityExerciseCounters(2, 2, 16, 16))
                passed += phase

                phase = expectedCases[7]
                val disconnected = async { runCatching { peers.first().call(RpcCapacityExercises.hold, "disconnect") } }
                    .also { active += it }
                awaitState(CapacityExerciseCounters(3, 2, 16, 16))
                peers.first().disconnect()
                add("disconnects")
                val interruption = disconnected.await().exceptionOrNull()
                check(interruption is RpcFailure && interruption.kind == RpcFailureKind.UnknownOutcome &&
                    interruption.phase == RpcFailurePhase.AwaitingResponse && interruption.requestId != null &&
                    interruption.executionEvidence == RpcExecutionEvidence.MayHaveExecuted)
                add("disconnectUnknownOutcomes")
                peers.first().reconnect()
                add("reconnects")
                // Remote work retains the original10-second deadline if closing the link cannot cancel it.
                awaitState(CapacityExerciseCounters(3, 3, 16, 16), boundMillis = 12_000)
                echo(peers.first())
                echo(observer)
                passed += phase

                phase = expectedCases[8]
                for (batch in peers.chunked(16)) {
                    batch.map { peer -> async { echo(peer) }.also { active += it } }.awaitAll()
                }
            } else {
                phase = expectedCases[1]
                repeat(CAPACITY_CHURN_ROUNDS) {
                    for (batch in peers.chunked(2)) {
                        batch.map { peer -> async { peer.disconnect(); add("disconnects") }.also { active += it } }
                            .awaitAll()
                        // Exactly the original clients/identities reconnect; the two-per-source limit is unchanged.
                        batch.map { peer ->
                            async { peer.reconnect(); add("reconnects"); echo(peer) }.also { active += it }
                        }.awaitAll()
                    }
                    fullCohort()
                    add("churnRounds")
                }
                passed += phase
                phase = expectedCases[2]
            }
            val after = fullCohort()
            set("hostConnectionsAfter", after.distinctAuthenticatedClients.toLong())
            set("hostRunningAfter", after.diagnostics.runningCalls.toLong())
            set("hostQueuedAfter", after.diagnostics.queuedCalls.toLong())
            check(metrics.getValue("echoResponses").get() == metrics.getValue("expectedEchoResponses").get())
            passed += phase
            check(passed == expectedCases)
            mechanical = true
        }
    } catch (cancelled: CancellationException) {
        if (!currentCoroutineContext().isActive) throw cancelled
    } catch (_: Exception) {
        // Fixed case names identify the failed control. No peer, payload, raw failure text or stack is exported.
    } finally {
        withContext(NonCancellable) { active.forEach { it.cancelAndJoin() } }
        set("actualDurationNanos", (nowNanos() - started).coerceAtLeast(0))
    }
    CapacityControlOutcome(mode, peers.size, mechanical, passed.toList(), if (mechanical) null else phase,
        metrics.mapValues { it.value.get() })
}
