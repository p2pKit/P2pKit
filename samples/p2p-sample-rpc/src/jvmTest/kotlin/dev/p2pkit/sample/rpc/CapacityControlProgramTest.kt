package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRequestId
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.selects.select
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.boolean
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.time.Duration

/** These controls test the campaign program and actual synthetic handlers, not network qualification. */
@OptIn(ExperimentalCoroutinesApi::class)
class CapacityControlProgramTest {
    private class Group(val scope: CoroutineScope) {
        val host = CapacityExerciseHostState()
        val remote = mutableListOf<Job>()
        var connecting = 0
        var maximumConnecting = 0
        var corruptEcho = false
        var omitDeniedEvidence = false
        var failBeforeRemoteEntry = false
        lateinit var peers: List<Peer>
        fun failure(kind: RpcFailureKind, evidence: RpcExecutionEvidence): RpcFailure {
            // Only this JVM program test constructs an opaque fixture ID. Production always obtains it from RPC.
            val constructor = RpcRequestId::class.java.getDeclaredConstructor(String::class.java)
            constructor.isAccessible = true
            return RpcFailure(kind, RpcFailurePhase.AwaitingResponse,
                if (omitDeniedEvidence && kind == RpcFailureKind.Unauthorized) null else
                    constructor.newInstance("a".repeat(32)), evidence)
        }

        suspend fun sample(): RpcCapacityHostSnapshot {
            delay(1)
            val current = host.snapshot()
            return RpcCapacityHostSnapshot(peers.count { it.state == RpcConnectionState.Ready },
                RpcDiagnostics(runningCalls = (current.holdEntered - current.holdRetired +
                    current.slowEntered - current.slowRetired).toInt()))
        }
    }

    private class Peer(private val group: Group) : CapacityControlPeer {
        override var state: RpcConnectionState = RpcConnectionState.Ready
        var reconnects = 0
        private var disconnected: CompletableDeferred<Unit>? = null

        override suspend fun call(
            procedure: RpcProcedure<String, String, String>, value: String, timeout: Duration,
        ): RpcReply<String, String> = when (procedure) {
            RpcCapacityExercises.echo -> RpcReply.Success(if (group.corruptEcho) "wrong-correlation" else value)
            RpcCapacityExercises.reject -> RpcReply.ApplicationError("synthetic")
            RpcCapacityExercises.denied -> throw group.failure(RpcFailureKind.Unauthorized,
                RpcExecutionEvidence.RejectedBeforeExecution)
            RpcCapacityExercises.state -> RpcReply.Success(group.host.snapshot().record())
            RpcCapacityExercises.slow -> group.host.slow(value)
            RpcCapacityExercises.hold -> hold(value, timeout)
            else -> error("Unknown synthetic procedure")
        }

        private suspend fun hold(value: String, timeout: Duration): RpcReply<String, String> {
            if (group.failBeforeRemoteEntry) throw group.failure(RpcFailureKind.DeadlineExceeded,
                RpcExecutionEvidence.NotSent)
            val lost = CompletableDeferred<Unit>()
            disconnected = lost
            val worker = group.scope.async(start = CoroutineStart.UNDISPATCHED) {
                withTimeout(timeout.inWholeMilliseconds) { group.host.hold(value) }
            }.also { group.remote += it }
            try {
                return select {
                    worker.onAwait { error("A held handler must not return") }
                    lost.onAwait {
                        throw group.failure(RpcFailureKind.UnknownOutcome, RpcExecutionEvidence.MayHaveExecuted)
                    }
                }
            } catch (_: TimeoutCancellationException) {
                throw group.failure(RpcFailureKind.DeadlineExceeded, RpcExecutionEvidence.MayHaveExecuted)
            } finally {
                disconnected = null
                // A link loss retains the real remote deadline; ordinary cancellation stops remote work.
                if (!lost.isCompleted) withContext(NonCancellable) { worker.cancelAndJoin() }
            }
        }

        override suspend fun disconnect() {
            state = RpcConnectionState.Closed
            disconnected?.complete(Unit)
        }

        override suspend fun reconnect() {
            group.connecting++
            group.maximumConnecting = maxOf(group.maximumConnecting, group.connecting)
            try {
                delay(1)
                state = RpcConnectionState.Ready
                reconnects++
            } finally { group.connecting-- }
        }
    }

    private fun TestScope.group(clients: Int): Group = Group(backgroundScope).also { group ->
        group.peers = List(clients) { Peer(group) }
    }

    @Test
    fun allSelectedClientsAndRemoteOutcomesAreCountedSeparatelyFromCapacity() = runTest {
        for (clients in listOf(128, 256)) {
            val group = group(clients)
            val outcome = runCapacityControlProgram("correctness", group.peers, group::sample,
                nowNanos = { testScheduler.currentTime * 1_000_000 })
            assertTrue(outcome.mechanical)
            assertEquals(CAPACITY_CORRECTNESS_CASES, outcome.passedCases)
            assertEquals(clients * 3L + 5, outcome.measurements["echoResponses"])
            assertEquals(3L, outcome.measurements["holdEntered"])
            assertEquals(3L, outcome.measurements["holdRetired"])
            assertEquals(16L, outcome.measurements["slowHandlerResponses"])
            assertTrue(group.remote.none { it.isActive })
            assertTrue(group.peers.all { it.state == RpcConnectionState.Ready })
            val report = Json.parseToJsonElement(outcome.json()).jsonObject
            assertFalse(report.getValue("capacityQualified").jsonPrimitive.boolean)
            assertFalse(report.getValue("trueSlowConsumerQualified").jsonPrimitive.boolean)
        }
    }

    @Test
    fun fiveChurnRoundsReconnectOnlyOriginalClientsInBatchesOfAtMostTwo() = runTest {
        for (clients in listOf(128, 256)) {
            val group = group(clients)
            val originals = group.peers.toList()
            val outcome = runCapacityControlProgram("churn", group.peers, group::sample,
                nowNanos = { testScheduler.currentTime * 1_000_000 })
            assertTrue(outcome.mechanical)
            assertEquals(CAPACITY_CHURN_CASES, outcome.passedCases)
            assertEquals(clients * 5L, outcome.measurements["echoResponses"])
            assertEquals(clients * 5L, outcome.measurements["reconnects"])
            assertEquals(originals, group.peers)
            assertTrue(group.peers.all { it.reconnects == 5 && it.state == RpcConnectionState.Ready })
            assertTrue(group.maximumConnecting <= 2)
            assertEquals(0, group.connecting)
        }
    }

    @Test
    fun localTimeoutBeforeHandlerEntryCannotBecomeASentDeadlinePass() = runTest {
        val group = group(128).apply { failBeforeRemoteEntry = true }
        val outcome = runCapacityControlProgram("correctness", group.peers, group::sample,
            nowNanos = { testScheduler.currentTime * 1_000_000 })
        assertFalse(outcome.mechanical)
        assertEquals("sent-deadline", outcome.failureCase)
        assertEquals(0L, outcome.measurements["sentDeadlineFailures"])
        assertEquals(0L, outcome.measurements["holdEntered"])
        assertTrue(group.remote.none { it.isActive })
    }

    @Test
    fun missingTypedExecutionEvidenceAndIncorrectCorrelationRemainFailures() = runTest {
        for ((configure, failedCase) in listOf<Pair<(Group) -> Unit, String>>(
            ({ group: Group -> group.omitDeniedEvidence = true }) to "procedure-authorization",
            ({ group: Group -> group.corruptEcho = true }) to "concurrent-correlation",
        )) {
            val group = group(128).also(configure)
            val outcome = runCapacityControlProgram("correctness", group.peers, group::sample,
                nowNanos = { testScheduler.currentTime * 1_000_000 })
            assertFalse(outcome.mechanical)
            assertEquals(failedCase, outcome.failureCase)
            assertTrue(group.remote.none { it.isActive })
        }
    }

    @Test
    fun externalCancellationRetiresEveryOwnedCallBeforeReturning() = runTest {
        val group = group(128)
        val program = async {
            runCapacityControlProgram("correctness", group.peers, group::sample,
                nowNanos = { testScheduler.currentTime * 1_000_000 })
        }
        withTimeout(1_000) { while (group.host.snapshot().holdEntered == 0L) delay(1) }
        program.cancelAndJoin()
        assertTrue(program.isCancelled)
        assertEquals(group.host.snapshot().holdEntered, group.host.snapshot().holdRetired)
        assertTrue(group.remote.none { it.isActive })
    }
}
