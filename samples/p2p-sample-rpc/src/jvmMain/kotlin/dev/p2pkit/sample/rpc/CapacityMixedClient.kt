package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcConnectionState
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
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put

internal suspend fun runMixedCapacity(
    generated: List<RpcClient>, nonce: String, sampleHost: suspend () -> RpcCapacityHostSnapshot,
) = supervisorScope {
    require(generated.size == MixedCapacityWire.GENERATED)
    val anchor = generated.first()
    var generators = 0
    var remoteReplies = 0
    var released = false
    var phoneDisconnected = false
    var phase = "await-phone"
    var passed = false

    suspend fun control(action: String) = anchor.call(MixedCapacityWire.control, "$nonce/$action")

    try {
        withTimeout(160_000) {
            // Host telemetry and its own authenticated ledger must agree. Rejected "open"
            // never advances the Host state. This wait is provisioning, not steady workload.
            withTimeout(120_000) {
                while (true) {
                    check(generated.all { it.state.value == RpcConnectionState.Ready })
                    if (sampleHost().distinctAuthenticatedClients == 256 &&
                        control("open") == RpcReply.Success("open")
                    ) break
                    delay(100)
                }
            }
            phase = "generator-probes"
            val payload = "$nonce/generator"
            for (batch in generated.chunked(16)) {
                val replies = batch.map { peer -> async { peer.call(MixedCapacityWire.probe, payload) } }.awaitAll()
                for (reply in replies) {
                    check(reply == RpcReply.Success(payload))
                    generators++
                }
            }
            phase = "phone-confirmation"
            val complete = RpcReply.Success("255,20,true")
            withTimeout(15_000) {
                while (true) {
                    val result = control("inspect")
                    check(result is RpcReply.Success && result.value.startsWith("255,"))
                    if (result == complete) break
                    delay(100)
                }
            }
            remoteReplies = MixedCapacityWire.PHONE_REPLIES
            phase = "release-original-cohort"
            check(control("release") == complete)
            released = true
            withTimeout(10_000) {
                while (sampleHost().distinctAuthenticatedClients != generated.size) {
                    check(generated.all { it.state.value == RpcConnectionState.Ready })
                    delay(100)
                }
            }
            check(generated.all { it.state.value == RpcConnectionState.Ready })
            phoneDisconnected = true
            passed = true
        }
    } catch (failure: CancellationException) {
        if (!currentCoroutineContext().isActive) throw failure
    } catch (_: Exception) {
        // Retain the bounded phase and original partial counts.
    }

    buildJsonObject {
        put("schema", 2)
        put("clientCount", 256)
        put("mode", "mixed")
        put("scope", "MIXED_CONCURRENT_ROSTER_PENDING_PHYSICAL_CLIENT_RECORD")
        put("status", if (passed) "PENDING_RESOURCE_AND_NETWORK_REVIEW" else "FAIL")
        put("capacityQualified", false)
        put("failureCase", if (passed) JsonNull else JsonPrimitive(phase))
        put("cleanup", "AWAIT_FINAL_RECORD")
        put("generatorReplies", generators)
        put("authenticatedPhoneRepliesVerified", remoteReplies)
        put("cohortReleased", released)
        put("phoneDisconnected", phoneDisconnected)
    }
}
