package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.SessionConnectionInfo
import dev.p2pkit.core.security.payloadSha256
import dev.p2pkit.rpc.RpcApplicationSession
import dev.p2pkit.rpc.RpcAuthorizationOperation
import dev.p2pkit.rpc.RpcAuthorizationScope
import dev.p2pkit.rpc.RpcCallObservation
import dev.p2pkit.rpc.RpcCallStage
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRequestId
import dev.p2pkit.rpc.RpcResultAcceptance
import dev.p2pkit.rpc.RpcRetry
import dev.p2pkit.rpc.RpcRetryAdvice
import dev.p2pkit.rpc.RpcRetrySafety
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.serialization.builtins.serializer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotEquals
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlin.time.Duration
import kotlin.time.Duration.Companion.seconds

@OptIn(ExperimentalCoroutinesApi::class)
class RpcResultAcceptanceTest {
    // Extra immutable state prevents coroutine-debug stack-trace recovery from copying this fixture.
    private class AcceptanceFailure(val stage: String) : Exception(stage)

    private val procedure = RpcProcedure("accept.echo", 1,
        String.serializer(), String.serializer(), String.serializer())

    private class Fixture(
        val budget: PayloadBudget, val host: RpcHostEngine, val client: RpcClientEngine,
        val hostLink: RpcTestLink, val clientLink: RpcTestLink,
    ) {
        val receipts get() = clientLink.sent.filter { it.kind == WireKind.Receipt }
        val invokes get() = clientLink.sent.filter { it.kind == WireKind.Invoke }

        suspend fun status(invocation: WireMessage): WireMessage {
            hostLink.clearSent()
            val message = WireMessage(WireKind.Status, invocation.id, invocation.incarnation,
                invocation.name, invocation.version, attempt = 2,
                body = OwnedBytes.copy(payloadSha256(checkNotNull(invocation.body).bytes), budget))
            host.deliver(hostLink, message)
            return hostLink.sent.last()
        }

        suspend fun close() {
            try { client.close() } finally {
                host.close()
                clientLink.clearSent()
                hostLink.clearSent()
            }
            assertEquals(0, client.diagnostics.value.runningCalls)
            assertEquals(0, client.diagnostics.value.queuedCalls)
            assertEquals(0L, budget.retainedBytes.value)
        }
    }

    private suspend fun TestScope.fixture(
        descriptor: RegisteredProcedure = registeredProcedure(procedure, { true }) { _, value ->
            RpcReply.Success(value)
        },
        clockOffset: () -> Long = { 0 },
    ): Fixture {
        val budget = PayloadBudget(16L * 1_048_576)
        val clock = RpcClock { testScheduler.currentTime + clockOffset() }
        val client = RpcClientEngine(backgroundScope, budget, clock, jitter = { 0 })
        val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            clock, { true }, TEST_INCARNATION)
        val hostLink = RpcTestLink()
        val clientLink = RpcTestLink(1)
        host.attach(hostLink)
        hostLink.onSend = { client.onMessage(clientLink, it) }
        clientLink.onSend = { host.onMessage(hostLink, it) }
        client.attach(clientLink)
        runCurrent()
        return Fixture(budget, host, client, hostLink, clientLink)
    }

    @Test
    fun receiptWaitsForValidationAndDurableCommitAndHasExactAssociation() = runTest {
        val f = fixture()
        try {
            val commit = CompletableDeferred<Unit>()
            var offered: RpcResultAcceptance<String, String>? = null
            var persisted = false
            val observation = RpcCallObservation()
            val call = async {
                f.client.callWithDetails(procedure, "private-result", 10.seconds, RpcRetry.RecoverOnly(),
                    observation) {
                    offered = it
                    assertEquals("private-result", assertIs<RpcReply.Success<String>>(it.details.reply).value)
                    commit.await()
                    persisted = true
                }
            }
            runCurrent()
            assertFalse(call.isCompleted)
            assertTrue(f.receipts.isEmpty())
            assertEquals(0L, f.client.requestTotals.value.succeeded)
            val context = checkNotNull(offered)
            val invocation = f.invokes.single()
            assertEquals(invocation.id, context.details.requestId.value)
            assertEquals(f.clientLink.identity.fingerprint, context.hostFingerprint)
            assertEquals(TEST_INCARNATION, context.hostIncarnation)
            assertEquals(procedure.name, context.procedureName)
            assertEquals(procedure.version, context.procedureVersion)
            assertFalse(context.toString().contains("private-result"))
            assertFalse(context.toString().contains(context.hostFingerprint.value))
            assertEquals(WireKind.Success, f.status(invocation).kind)
            advanceTimeBy(250)
            commit.complete(Unit)
            runCurrent()
            val details = call.await()
            assertTrue(persisted)
            assertEquals(context.details.requestId, details.requestId)
            assertEquals(250L, details.elapsedMillis)
            assertEquals(RpcCallStage.Succeeded, observation.progress.value.stage)
            val receipt = f.receipts.single()
            assertEquals(invocation.id, receipt.id)
            assertEquals(invocation.incarnation, receipt.incarnation)
            assertEquals(invocation.name, receipt.name)
            assertEquals(invocation.version, receipt.version)
            assertTrue(payloadSha256(checkNotNull(invocation.body).bytes)
                .contentEquals(checkNotNull(receipt.body).bytes))
            assertEquals(WireFailure.ResultUnavailable.code, f.status(invocation).code)
            assertEquals(1L, f.host.diagnostics.value.completedCalls)
        } finally { f.close() }
    }

    @Test
    fun validationAndPersistenceExceptionsRetainResultAndNeverRetryAcceptanceOrInvocation() = runTest {
        val idempotent = RpcProcedure("accept.echo", 1, String.serializer(), String.serializer(),
            String.serializer(), RpcRetrySafety.Idempotent)
        for (problem in listOf(AcceptanceFailure("validation"), AcceptanceFailure("durable write"))) {
            var executions = 0
            val f = fixture(registeredProcedure(idempotent, { true }) { _, value ->
                executions++
                RpcReply.Success(value)
            })
            try {
                var acceptances = 0
                val observation = RpcCallObservation()
                val failure = runCatching {
                    f.client.callWithDetails(idempotent, "q", 10.seconds, RpcRetry.Idempotent(), observation) {
                        acceptances++
                        throw problem
                    }
                }.exceptionOrNull()
                assertSame(problem, failure)
                assertEquals(1, acceptances)
                assertEquals(1, executions)
                assertTrue(f.receipts.isEmpty())
                assertEquals(1, f.invokes.size)
                assertEquals(RpcCallStage.Failed, observation.progress.value.stage)
                assertEquals(RpcExecutionEvidence.HandlerFinished, observation.progress.value.executionEvidence)
                assertEquals(1L, f.client.requestTotals.value.failed)
                assertEquals(0L, f.client.diagnostics.value.completedCalls)
                assertEquals(WireKind.Success, f.status(f.invokes.single()).kind)
            } finally { f.close() }
        }
    }

    @Test
    fun cancellationDuringAcceptanceNeverReceiptsAndDrainsPendingResources() = runTest {
        val f = fixture()
        try {
            val observation = RpcCallObservation()
            val entered = CompletableDeferred<Unit>()
            val call = async {
                f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly(), observation) {
                    entered.complete(Unit)
                    awaitCancellation()
                }
            }
            runCurrent()
            assertTrue(entered.isCompleted)
            call.cancel()
            runCurrent()
            call.join()
            assertIs<CancellationException>(runCatching { call.await() }.exceptionOrNull())
            assertTrue(f.receipts.isEmpty())
            assertEquals(RpcCallStage.Cancelled, observation.progress.value.stage)
            assertEquals(1L, f.client.requestTotals.value.cancelled)
            assertEquals(WireKind.Success, f.status(f.invokes.single()).kind)
        } finally { f.close() }
    }

    @Test
    fun callbackCannotSwallowCallerCancellationAndTriggerReceipt() = runTest {
        val f = fixture()
        try {
            val call = async {
                f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) {
                    currentCoroutineContext().cancel()
                    withContext(NonCancellable) { /* Simulate completing cleanup after cancellation. */ }
                }
            }
            runCurrent()
            assertIs<CancellationException>(runCatching { call.await() }.exceptionOrNull())
            assertTrue(f.receipts.isEmpty())
            assertEquals(WireKind.Success, f.status(f.invokes.single()).kind)
        } finally { f.close() }
    }

    @Test
    fun callbackCancellationOrFatalFailureNeverReceiptsAndReleasesTheCall() = runTest {
        for (problem in listOf(CancellationException("application cancelled"), AssertionError("fatal validation"))) {
            val f = fixture()
            try {
                val result = runCatching {
                    f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) { throw problem }
                }
                assertEquals(problem::class, checkNotNull(result.exceptionOrNull())::class)
                assertTrue(f.receipts.isEmpty())
                assertEquals(WireKind.Success, f.status(f.invokes.single()).kind)
                assertEquals(0, f.client.diagnostics.value.runningCalls)
                assertEquals(0L, f.client.diagnostics.value.completedCalls)
            } finally { f.close() }
        }
    }

    @Test
    fun nestedRpcFailureDuringAcceptanceKeepsItsOwnRequestIdentityAndRetryAdvice() = runTest {
        val f = fixture()
        try {
            val nested = RpcFailure(RpcFailureKind.NotConnected, RpcFailurePhase.Sending,
                RpcRequestId(TEST_SECOND), RpcExecutionEvidence.RejectedBeforeExecution,
                RpcRetryAdvice.SafeBeforeExecution)
            val observation = RpcCallObservation()
            val result = runCatching {
                f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly(), observation) {
                    throw nested
                }
            }
            assertSame(nested, result.exceptionOrNull())
            assertEquals(TEST_SECOND, nested.requestId?.value)
            assertEquals(RpcRetryAdvice.SafeBeforeExecution, nested.retryAdvice)
            assertNotEquals(TEST_SECOND, observation.progress.value.requestId)
            assertEquals(RpcExecutionEvidence.HandlerFinished, observation.progress.value.executionEvidence)
            assertEquals(RpcCallStage.Failed, observation.progress.value.stage)
            assertTrue(f.receipts.isEmpty())
            assertEquals(WireKind.Success, f.status(f.invokes.single()).kind)
        } finally { f.close() }
    }

    @Test
    fun acceptanceUsesTheOriginalDeadline() = runTest {
        val f = fixture()
        try {
            val call = async {
                runCatching {
                    f.client.callWithDetails(procedure, "q", 1.seconds, RpcRetry.RecoverOnly()) {
                        awaitCancellation()
                    }
                }
            }
            runCurrent()
            advanceTimeBy(1_000)
            runCurrent()
            val failure = assertIs<RpcFailure>(call.await().exceptionOrNull())
            assertEquals(RpcFailureKind.DeadlineExceeded, failure.kind)
            assertEquals(RpcExecutionEvidence.HandlerFinished, failure.executionEvidence)
            assertTrue(f.receipts.isEmpty())
            assertEquals(1L, f.client.requestTotals.value.timedOut)
            assertEquals(WireKind.Success, f.status(f.invokes.single()).kind)
        } finally { f.close() }
    }

    @Test
    fun nonSuspendingAcceptanceCannotReceiptAfterTheMonotonicDeadline() = runTest {
        var elapsed = 0L
        val f = fixture(clockOffset = { elapsed })
        try {
            val failure = runCatching {
                f.client.callWithDetails(procedure, "q", 1.seconds, RpcRetry.RecoverOnly()) {
                    // A blocking callback may delay the coroutine timeout dispatcher; the clock still advances.
                    elapsed = 1_000
                }
            }.exceptionOrNull()
            assertEquals(RpcFailureKind.DeadlineExceeded, assertIs<RpcFailure>(failure).kind)
            assertTrue(f.receipts.isEmpty())
            assertEquals(1L, f.client.requestTotals.value.timedOut)
        } finally { f.close() }
    }

    @Test
    fun businessErrorMustAlsoPassAcceptanceBeforeReceipt() = runTest {
        val f = fixture(registeredProcedure(procedure, { true }) { _, value -> RpcReply.ApplicationError(value) })
        try {
            val rejected = runCatching {
                f.client.callWithDetails(procedure, "rejected", 10.seconds, RpcRetry.RecoverOnly()) {
                    assertEquals("rejected", assertIs<RpcReply.ApplicationError<String>>(it.details.reply).error)
                    error("Cannot persist rejection")
                }
            }
            assertTrue(rejected.isFailure)
            assertTrue(f.receipts.isEmpty())
            assertEquals(WireKind.ApplicationError, f.status(f.invokes.single()).kind)
            val accepted = f.client.callWithDetails(procedure, "accepted", 10.seconds, RpcRetry.RecoverOnly()) {
                assertTrue(f.receipts.isEmpty())
                assertIs<RpcReply.ApplicationError<String>>(it.details.reply)
            }
            assertEquals(accepted.requestId.value, f.receipts.single().id)
            assertEquals(1L, f.client.requestTotals.value.businessErrors)
        } finally { f.close() }
    }

    @Test
    fun infrastructureFailuresAndInvalidPayloadNeverReachAcceptanceOrReceipt() = runTest {
        for (invalidPayload in listOf(false, true)) {
            val f = fixture(registeredProcedure(procedure, { true }) { _, value ->
                if (!invalidPayload) error("Handler failure") else RpcReply.Success(value)
            })
            try {
                if (invalidPayload) f.hostLink.onSend = { message ->
                    if (message.kind == WireKind.Success) {
                        val corrupted = message.copy(body = testBody("not-json", f.budget))
                        try { f.client.onMessage(f.clientLink, corrupted) } finally { corrupted.release() }
                    } else f.client.onMessage(f.clientLink, message)
                }
                var callbacks = 0
                val outcome = runCatching {
                    f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) { callbacks++ }
                }
                val failure = assertIs<RpcFailure>(outcome.exceptionOrNull())
                assertEquals(if (invalidPayload) RpcFailureKind.InvalidPayload else RpcFailureKind.HandlerFailed,
                    failure.kind)
                assertEquals(0, callbacks)
                assertTrue(f.receipts.isEmpty())
            } finally { f.close() }
        }
    }

    @Test
    fun lostResponseRecoversSameRequestThenAcceptsOnceWithoutReinvocation() = runTest {
        var executions = 0
        val f = fixture(registeredProcedure(procedure, { true }) { _, value ->
            executions++
            RpcReply.Success(value)
        })
        try {
            var lost = false
            f.hostLink.onSend = {
                if (it.kind == WireKind.Success && !lost) lost = true else f.client.onMessage(f.clientLink, it)
            }
            var callbacks = 0
            val call = async {
                f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) { callbacks++ }
            }
            runCurrent()
            assertEquals(0, callbacks)
            advanceTimeBy(5_001)
            runCurrent()
            val details = call.await()
            assertEquals(1, callbacks)
            assertEquals(1, executions)
            assertEquals(1, f.invokes.size)
            assertEquals(f.invokes.single().id, details.requestId.value)
            assertEquals(details.requestId.value, f.receipts.single().id)
            assertEquals(1, f.clientLink.sent.count { it.kind == WireKind.Status })
        } finally { f.close() }
    }

    @Test
    fun lostReceiptKeepsRetainedResultAndDuplicateInvokeDoesNotReexecute() = runTest {
        var executions = 0
        val f = fixture(registeredProcedure(procedure, { true }) { _, value ->
            executions++
            RpcReply.Success(value)
        })
        try {
            f.clientLink.onSend = { if (it.kind != WireKind.Receipt) f.host.onMessage(f.hostLink, it) }
            f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) { }
            val invocation = f.invokes.single()
            assertEquals(WireKind.Success, f.status(invocation).kind)
            f.host.onMessage(f.hostLink, invocation)
            runCurrent()
            assertEquals(WireKind.Success, f.hostLink.sent.last().kind)
            assertEquals(1, executions)
            advanceTimeBy(30_001)
            assertEquals(WireFailure.ResultUnavailable.code, f.status(invocation).code)
            assertEquals(1, executions)
        } finally { f.close() }
    }

    @Test
    fun concurrentAcceptancesCannotReceiptAnotherRetainedResult() = runTest {
        val f = fixture()
        try {
            val gate = CompletableDeferred<Unit>()
            val first = async {
                f.client.callWithDetails(procedure, "first", 10.seconds, RpcRetry.RecoverOnly()) { gate.await() }
            }
            runCurrent()
            val firstInvocation = f.invokes.single()
            val second = f.client.callWithDetails(procedure, "second", 10.seconds, RpcRetry.RecoverOnly()) { }
            assertNotEquals(firstInvocation.id, second.requestId.value)
            assertEquals(second.requestId.value, f.receipts.single().id)
            assertEquals(WireKind.Success, f.status(firstInvocation).kind)
            gate.complete(Unit)
            runCurrent()
            assertEquals(firstInvocation.id, first.await().requestId.value)
            assertEquals(2, f.receipts.size)
        } finally { f.close() }
    }

    @Test
    fun disconnectOrGenerationChangeDuringAcceptanceCannotSendReceiptToReplacement() = runTest {
        for (disconnect in listOf(false, true)) {
            val f = fixture()
            try {
                val result = f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) {
                    if (disconnect) f.client.close()
                    else f.clientLink.generation.value = SessionConnectionInfo(2)
                }
                assertIs<RpcReply.Success<String>>(result.reply)
                assertTrue(f.receipts.isEmpty())
                assertEquals(WireKind.Success, f.status(f.invokes.single()).kind)
            } finally { f.close() }
        }
    }

    @Test
    fun cancellationWhileReceiptIsQueuedRetiresItBeforeAnyTransmission() = runTest {
        val f = fixture()
        try {
            val call = async {
                f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) {
                    f.clientLink.paused = true
                }
            }
            runCurrent()
            assertEquals(1, f.clientLink.queued.size)
            call.cancel()
            runCurrent()
            call.join()
            f.clientLink.deliver(f.clientLink.queued.single())
            assertTrue(f.receipts.isEmpty())
            assertEquals(WireKind.Success, f.status(f.invokes.single()).kind)
        } finally { f.close() }
    }

    @Test
    fun boundedReceiptQueueTimeoutReturnsAcceptedResultAndRetiresTheQueuedReceipt() = runTest {
        val f = fixture()
        try {
            val call = async {
                f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) {
                    f.clientLink.paused = true
                }
            }
            runCurrent()
            advanceTimeBy(1_000)
            runCurrent()
            assertIs<RpcReply.Success<String>>(call.await().reply)
            f.clientLink.deliver(f.clientLink.queued.single())
            assertTrue(f.receipts.isEmpty())
            assertEquals(1L, f.client.requestTotals.value.succeeded)
            assertEquals(WireKind.Success, f.status(f.invokes.single()).kind)
        } finally { f.close() }
    }

    @Test
    fun generationChangeAfterReceiptQueueingCannotTransmitOnTheReplacement() = runTest {
        val f = fixture()
        try {
            val call = async {
                f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) {
                    f.clientLink.paused = true
                }
            }
            runCurrent()
            val ticket = f.clientLink.queued.single()
            f.clientLink.generation.value = SessionConnectionInfo(2)
            f.clientLink.deliver(ticket)
            runCurrent()
            assertFalse(ticket.started)
            assertIs<RpcReply.Success<String>>(call.await().reply)
            assertTrue(f.receipts.isEmpty())
        } finally { f.close() }
    }

    @Test
    fun suspendedAcceptanceRetainsTheExistingOutstandingCallBound() = runTest {
        val f = fixture()
        try {
            val gate = CompletableDeferred<Unit>()
            val calls = List(8) { index ->
                async {
                    f.client.callWithDetails(procedure, "q$index", 10.seconds, RpcRetry.RecoverOnly()) {
                        gate.await()
                    }
                }
            }
            runCurrent()
            assertEquals(8, f.client.diagnostics.value.runningCalls)
            val refused = runCatching {
                f.client.callWithDetails(procedure, "ninth", 10.seconds, RpcRetry.RecoverOnly()) {
                    error("Refused work must never enter acceptance")
                }
            }
            assertEquals(RpcFailureKind.Overloaded, assertIs<RpcFailure>(refused.exceptionOrNull()).kind)
            assertTrue(f.receipts.isEmpty())
            gate.complete(Unit)
            runCurrent()
            calls.forEach { it.await() }
            assertEquals(8, f.receipts.size)
            assertEquals(0, f.client.diagnostics.value.runningCalls)
        } finally { f.close() }
    }

    @Test
    fun scopedReceiptStillRequiresFreshHostAuthorization() = runTest {
        val clock = RpcClock { testScheduler.currentTime }
        val session = RpcApplicationSession(testFingerprint(), "employee", "login", Duration.INFINITE, clock)
        val grant = RpcAuthorizationScope(session)
        var receiptsAllowed = true
        var receiptChecks = 0
        val descriptor = registeredScopedProcedure(procedure, { _, _ -> grant }, { context ->
            if (context.operation == RpcAuthorizationOperation.Receipt) {
                receiptChecks++
                receiptsAllowed
            } else true
        }) { _, value -> RpcReply.Success(value) }
        val f = fixture(descriptor)
        try {
            f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) {
                receiptsAllowed = false
            }
            assertEquals(1, receiptChecks)
            assertEquals(WireKind.Success, f.status(f.invokes.single()).kind)
        } finally { f.close() }
    }

    @Test
    fun legacyAutomaticReceiptRemainsIndependentOfOptInAcceptance() = runTest {
        val f = fixture()
        try {
            assertIs<RpcReply.Success<String>>(
                f.client.call(procedure, "legacy-call", 10.seconds, RpcRetry.RecoverOnly()))
            f.client.callWithDetails(procedure, "legacy-details", 10.seconds, RpcRetry.RecoverOnly())
            val observation = RpcCallObservation()
            f.client.callWithDetails(procedure, "legacy-observation", 10.seconds, RpcRetry.RecoverOnly(), observation)
            assertEquals(RpcCallStage.Succeeded, observation.progress.value.stage)
            assertEquals(3, f.receipts.size)
            assertEquals(3L, f.client.requestTotals.value.succeeded)
            for (invocation in f.invokes) assertEquals(WireFailure.ResultUnavailable.code, f.status(invocation).code)
        } finally { f.close() }
    }

    @Test
    fun mismatchedRequestProcedureIncarnationOrAttachmentNeverReachesAcceptance() = runTest {
        for (mismatch in listOf("request", "name", "version", "incarnation", "attachment")) {
            val f = fixture()
            val stranger = RpcTestLink(9)
            try {
                f.hostLink.onSend = { message ->
                    if (message.kind == WireKind.Success) {
                        val altered = message.copy(
                            id = if (mismatch == "request") TEST_SECOND else message.id,
                            name = if (mismatch == "name") "another.procedure" else message.name,
                            version = if (mismatch == "version") 2 else message.version,
                            incarnation = if (mismatch == "incarnation") TEST_SECOND else message.incarnation,
                        )
                        f.client.onMessage(if (mismatch == "attachment") stranger else f.clientLink, altered)
                    } else f.client.onMessage(f.clientLink, message)
                }
                var callbacks = 0
                val call = async {
                    runCatching {
                        f.client.callWithDetails(procedure, "q", 1.seconds, RpcRetry.RecoverOnly(1)) { callbacks++ }
                    }
                }
                runCurrent()
                advanceTimeBy(1_000)
                runCurrent()
                assertTrue(call.await().isFailure, mismatch)
                assertEquals(0, callbacks, mismatch)
                assertTrue(f.receipts.isEmpty(), mismatch)
            } finally {
                stranger.close()
                stranger.clearSent()
                f.close()
            }
        }
    }
}
