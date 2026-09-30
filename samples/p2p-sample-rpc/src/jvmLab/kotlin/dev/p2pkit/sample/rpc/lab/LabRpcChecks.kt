package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcClient
import dev.p2pkit.rpc.RpcEndpoint
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcHost
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcPlatform
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcTrustStore
import dev.p2pkit.rpc.jvm
import dev.p2pkit.sample.rpc.RpcCapacityContract
import dev.p2pkit.sample.rpc.RpcCapacityHost
import dev.p2pkit.sample.rpc.RpcCapacityHostSnapshot
import dev.p2pkit.transport.lan.OrganizationLan
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.util.concurrent.atomic.AtomicInteger
import kotlin.system.exitProcess
import kotlin.time.Duration.Companion.seconds

/** Lab-only lifecycle adapter; neither implementation substitutes for the real RpcHost. */
internal class LabRunningHost(
    val fingerprint: PeerFingerprint,
    val start: suspend () -> Unit,
    val endpoint: suspend () -> RpcEndpoint,
    val snapshot: () -> RpcCapacityHostSnapshot,
    val close: suspend () -> Unit,
) {
    companion object {
        fun capacity(host: RpcCapacityHost): LabRunningHost = LabRunningHost(
            host.fingerprint, host::start, host::endpoint, host::snapshot, host::close,
        )

        fun checks(host: RpcHost): LabRunningHost = LabRunningHost(
            host.fingerprint, host::start, host::endpoint,
            {
                RpcCapacityHostSnapshot(
                    host.connections.value.filter {
                        it.admission == PeerAdmission.Trusted && it.state == ConnectionState.Connected
                    }.mapNotNull { it.peer.fingerprint }.toSet().size,
                    host.diagnostics.value,
                )
            },
            host::close,
        )
    }
}

/** Fixed synthetic procedures exist ONLY in the explicitly selected correctness host. */
internal object LabRpcChecks {
    val cases: List<String> = listOf(
        "concurrent-correlation", "application-error", "procedure-authorization",
        "sent-deadline", "sent-cancellation", "close-during-call",
    )
    private fun procedure(name: String): RpcProcedure<String, String, String> = RpcProcedure(
        "lab.checks.$name", 1, String.serializer(), String.serializer(), String.serializer(),
        requestLimitBytes = 1024, responseLimitBytes = 1024, errorLimitBytes = 256,
    )
    val echo = procedure("echo")
    val reject = procedure("reject")
    val denied = procedure("denied")
    val hold = procedure("hold")
    val state = procedure("state")

    suspend fun host(
        platform: RpcPlatform, scope: CoroutineScope, lan: OrganizationLan,
        trust: RpcTrustStore, approved: Set<PeerFingerprint>,
    ): LabRunningHost {
        require(approved.size == 128)
        val pins = approved.toSet()
        val entered = AtomicInteger()
        val retired = AtomicInteger()
        val unauthorizedInvocations = AtomicInteger()
        val host = RpcHost.create(platform, scope) {
            appId = RpcCapacityContract.appId
            this.lan = lan
            trustStore = trust
            limits = RpcLimits.host128()
            advertise = false
            register(echo, authorize = { it.fingerprint in pins }) { _, value -> RpcReply.Success(value) }
            register(reject, authorize = { it.fingerprint in pins }) { _, _ -> RpcReply.ApplicationError("synthetic") }
            register(denied, authorize = { false }) { _, _ ->
                unauthorizedInvocations.incrementAndGet()
                RpcReply.Success("must-not-execute")
            }
            register(hold, authorize = { it.fingerprint in pins }) { _, value ->
                require(value in setOf("deadline", "cancel", "close"))
                entered.incrementAndGet()
                try { awaitCancellation() } finally { retired.incrementAndGet() }
            }
            register(state, authorize = { it.fingerprint in pins }) { _, _ ->
                RpcReply.Success("${entered.get()},${retired.get()},${unauthorizedInvocations.get()}")
            }
        }
        if (host.trust.fingerprints().toSet() != pins) {
            host.close()
            error("The correctness host requires exactly the provisioned synthetic peers")
        }
        return LabRunningHost.checks(host)
    }
}

/** Real separate-process TCP/RPC controls, not unit mocks or a capacity measurement. */
@JvmName("main")
public fun runRpcLocalChecks(args: Array<String>) {
    require(args.contentEquals(arrayOf("--owner-authorized-correctness-run")))
    var passed = false
    var cleaned = false
    var phase = "setup"
    val completed = mutableListOf<String>()
    try {
        runBlocking(Dispatchers.Default) {
            supervisorScope {
                val environment = LabEnvironment()
                val clients = mutableListOf<RpcClient>()
                try {
                    repeat(2) { index ->
                        val platform = RpcPlatform.jvm(environment.identityStore(index))
                        val trust = environment.trustStore(index)
                        clients += RpcClient.create(platform, this) {
                            appId = RpcCapacityContract.appId
                            lan = environment.lan
                            trustStore = trust
                        }
                    }
                    check(clients[0].fingerprint != clients[1].fingerprint)
                    clients.forEach { it.connect(environment.selectedHost) }
                    val first = clients[0]
                    val observer = clients[1]
                    suspend fun state(entered: Int, retired: Int, boundMillis: Long = 2_000) {
                        withTimeout(boundMillis) {
                            while (observer.call(LabRpcChecks.state, "") != RpcReply.Success("$entered,$retired,0")) {
                                delay(20)
                            }
                        }
                    }
                    suspend fun healthy() {
                        check(observer.call(LabRpcChecks.echo, "still-live") == RpcReply.Success("still-live"))
                    }
                    withTimeout(90_000) {
                        phase = LabRpcChecks.cases[0]
                        List(8) { index ->
                            async {
                                val body = "correlation-$index-" + "\u03a9\n\"\\".repeat(10)
                                check(clients[index % 2].call(LabRpcChecks.echo, body) == RpcReply.Success(body))
                            }
                        }.awaitAll()
                        completed += phase

                        phase = LabRpcChecks.cases[1]
                        check(first.call(LabRpcChecks.reject, "") == RpcReply.ApplicationError("synthetic"))
                        completed += phase

                        phase = LabRpcChecks.cases[2]
                        val denied = runCatching { first.call(LabRpcChecks.denied, "") }.exceptionOrNull()
                        check(denied is RpcFailure && denied.kind == RpcFailureKind.Unauthorized)
                        state(0, 0) // Also proves the denied handler was never entered.
                        completed += phase

                        phase = LabRpcChecks.cases[3]
                        val deadline = async {
                            runCatching { first.call(LabRpcChecks.hold, "deadline", timeout = 3.seconds) }
                        }
                        state(1, 0) // A remote application handler really started before the timeout.
                        val failure = deadline.await().exceptionOrNull()
                        check(failure is RpcFailure && failure.kind == RpcFailureKind.DeadlineExceeded &&
                            failure.requestId != null && failure.executionEvidence != RpcExecutionEvidence.NotSent)
                        state(1, 1)
                        healthy()
                        completed += phase

                        phase = LabRpcChecks.cases[4]
                        val cancelled = async { first.call(LabRpcChecks.hold, "cancel") }
                        state(2, 1)
                        cancelled.cancelAndJoin()
                        check(cancelled.isCancelled)
                        state(2, 2)
                        healthy()
                        completed += phase

                        phase = LabRpcChecks.cases[5]
                        val closing = async { runCatching { first.call(LabRpcChecks.hold, "close") } }
                        state(3, 2)
                        first.close()
                        val interrupted = closing.await().exceptionOrNull()
                        check(interrupted is RpcFailure && interrupted.kind == RpcFailureKind.UnknownOutcome &&
                            interrupted.requestId != null &&
                            interrupted.executionEvidence == RpcExecutionEvidence.MayHaveExecuted)
                        // A disconnect need not stop remote work. Its original 10-second deadline
                        // remains authoritative; do not assert immediate undo on connection close.
                        state(3, 3, 12_000)
                        first.close() // Retained/idempotent close, not another live connection.
                        val afterClose = runCatching { first.call(LabRpcChecks.echo, "") }.exceptionOrNull()
                        check(afterClose is RpcFailure && afterClose.kind == RpcFailureKind.Closed &&
                            afterClose.executionEvidence == RpcExecutionEvidence.NotSent)
                        healthy()
                        completed += phase
                    }
                    check(completed == LabRpcChecks.cases)
                    passed = true
                } finally {
                    withContext(NonCancellable) {
                        var failure: Exception? = null
                        for (client in clients) {
                            try { client.close() } catch (caught: Exception) { failure = caught }
                        }
                        try { environment.close() } catch (caught: Exception) { failure = caught }
                        failure?.let { throw it }
                        cleaned = true
                    }
                }
            }
        }
    } catch (_: Exception) {
        System.err.println("RPC_LOCAL_CHECK_FAILED phase=$phase; no raw cause or payload exported")
    } finally {
        println("RPC_CAPACITY_RESULT_JSON:" + buildJsonObject {
            put("schema", 1)
            put("mode", "correctness")
            put("scope", "REAL_SOCKET_CORRECTNESS_NOT_CAPACITY")
            put("status", if (passed) "PENDING_RESOURCE_AND_NETWORK_REVIEW" else "FAIL")
            put("capacityQualified", false)
            put("expectedCases", LabRpcChecks.cases.size)
            put("passedCases", buildJsonArray { completed.forEach { add(it) } })
        })
        println("RPC_CAPACITY_FINAL_JSON:" + buildJsonObject {
            put("schema", 1)
            put("mechanicalChecksPassed", passed)
            put("cleanupVerified", cleaned)
            put("capacityQualified", false)
        })
    }
    if (!passed || !cleaned) exitProcess(1)
}
