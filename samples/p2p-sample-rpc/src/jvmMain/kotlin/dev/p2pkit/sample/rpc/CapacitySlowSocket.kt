package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcReply
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
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

internal interface CapacitySocketPause : AutoCloseable {
    fun pause()
    fun observedConstrainedWindow(): Boolean
}

internal suspend fun runCapacitySlowSocket(
    target: RpcClient, witness: RpcClient, pause: CapacitySocketPause, clients: Int,
    sampleHost: suspend () -> RpcCapacityHostSnapshot,
): JsonObject = supervisorScope {
    capacityProfileLimits(clients)
    val start = System.nanoTime()
    val metrics = linkedMapOf("constrainedWindowHoldMillis" to 0L, "pendingWhilePaused" to 0L, "unaffectedEchoes" to 0L,
        "resumedLargeReplies" to 0L, "hostConnectionsBefore" to 0L, "hostConnectionsAfter" to 0L)
    var phase = "initial-cohort"
    var passed = false
    try {
        withTimeout(25_000) {
            val before = sampleHost()
            check(before.distinctAuthenticatedClients == clients)
            metrics["hostConnectionsBefore"] = clients.toLong()

            phase = "socket-read-hold"
            val payloads = listOf("a", "b").map { it.repeat(RpcCapacityContract.MAXIMUM_BODY_BYTES - 2) }
            val pending = try {
                pause.pause()
                val replies = payloads.map { payload ->
                    async { target.call(RpcCapacityContract.largeEcho, payload, 10.seconds) }
                }
                withTimeout(2_000) { while (!pause.observedConstrainedWindow()) delay(5) }
                val holdFrom = System.nanoTime()
                check(replies.none { it.isCompleted })
                metrics["pendingWhilePaused"] = replies.size.toLong()
                phase = "unaffected-peer"
                repeat(3) { index ->
                    val probe = "socket-witness-$index"
                    check(witness.call(RpcCapacityExercises.echo, probe, 1.seconds) == RpcReply.Success(probe))
                    check(pause.observedConstrainedWindow() && replies.none { it.isCompleted })
                    metrics["unaffectedEchoes"] = index + 1L
                    delay(300)
                }
                delay(150)
                check(pause.observedConstrainedWindow() && replies.none { it.isCompleted })
                metrics["constrainedWindowHoldMillis"] = (System.nanoTime() - holdFrom) / 1_000_000
                replies
            } finally {
                pause.close()
            }

            phase = "resumed-echoes"
            pending.awaitAll().forEachIndexed { index, reply ->
                check(reply == RpcReply.Success(payloads[index]))
                metrics["resumedLargeReplies"] = index + 1L
            }
            phase = "cohort-recovery"
            val after = sampleHost()
            check(after.distinctAuthenticatedClients == clients && after.diagnostics.queuedCalls == 0 &&
                after.diagnostics.runningCalls == 0)
            metrics["hostConnectionsAfter"] = clients.toLong()
            check(metrics.getValue("constrainedWindowHoldMillis") >= 1_000)
            passed = true
        }
    } catch (failure: CancellationException) {
        if (!currentCoroutineContext().isActive) throw failure
    } catch (_: Exception) {
        // Retain partial counts without logging peer identities or payloads.
    }
    buildJsonObject {
        put("schema", 2)
        put("clientCount", clients)
        put("mode", "socket-slow")
        put("scope", "DARWIN_TCP_CONSTRAINED_RECEIVE_WINDOW_PENDING_PHYSICAL_REVIEW")
        put("status", if (passed) "PENDING_RESOURCE_AND_NETWORK_REVIEW" else "FAIL")
        put("capacityQualified", false)
        put("failureCase", if (passed) JsonNull else JsonPrimitive(phase))
        put("cleanup", "AWAIT_FINAL_RECORD")
        put("measurements", JsonObject((metrics + ("elapsedNanos" to System.nanoTime() - start))
            .mapValues { JsonPrimitive(it.value) }))
    }
}
