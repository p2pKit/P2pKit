package dev.p2pkit.rpc.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.SessionConnectionInfo
import dev.p2pkit.rpc.RpcCallObservation
import dev.p2pkit.rpc.RpcCallStage
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import dev.p2pkit.rpc.RpcRetry
import dev.p2pkit.rpc.RpcRetrySafety
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.builtins.serializer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds

@OptIn(ExperimentalCoroutinesApi::class)
class RpcClientEngineTest {
    private val procedure = RpcProcedure("echo", 1, String.serializer(), String.serializer(), String.serializer())
    private class Fixture(
        val budget: PayloadBudget, val host: RpcHostEngine, val client: RpcClientEngine,
        val hostLink: RpcTestLink, val clientLink: RpcTestLink,
    ) {
        suspend fun close() {
            client.close(); host.close(); clientLink.clearSent(); hostLink.clearSent()
            assertEquals(0L, budget.retainedBytes.value)
        }
    }

    private suspend fun TestScope.fixture(descriptor: RegisteredProcedure): Fixture {
        val budget = PayloadBudget(16L * 1_048_576)
        val clock = RpcClock { testScheduler.currentTime }
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
    fun detailedRepliesExposeActualCorrelationWithoutLeakingPayloadThroughToString() = runTest {
        val seenIds = mutableListOf<String>()
        val f = fixture(registeredProcedure(procedure, { true }) { context, value ->
            seenIds += context.requestId.value
            if (value == "private-business-input") RpcReply.ApplicationError("private-business-error")
            else RpcReply.Success(value)
        })
        val successProgress = RpcCallObservation()
        val businessProgress = RpcCallObservation()
        val success = f.client.callWithDetails(procedure, "private-response", 10.seconds,
            RpcRetry.RecoverOnly(), successProgress)
        val business = f.client.callWithDetails(procedure, "private-business-input", 10.seconds,
            RpcRetry.RecoverOnly(), businessProgress)
        assertEquals(RpcCallStage.Succeeded, successProgress.progress.value.stage)
        assertEquals(RpcCallStage.BusinessError, businessProgress.progress.value.stage)
        assertEquals(success.requestId.value, successProgress.progress.value.requestId)
        assertEquals(business.requestId.value, businessProgress.progress.value.requestId)
        assertEquals(TEST_INCARNATION, successProgress.progress.value.hostIncarnation)
        assertEquals(f.clientLink.identity.fingerprint?.value, successProgress.progress.value.peerFingerprint)
        assertEquals(RpcExecutionEvidence.HandlerFinished, successProgress.progress.value.executionEvidence)
        assertEquals(0, f.client.diagnostics.value.queuedCalls)
        assertEquals("private-response", assertIs<RpcReply.Success<String>>(success.reply).value)
        assertEquals("private-business-error", assertIs<RpcReply.ApplicationError<String>>(business.reply).error)
        assertEquals(seenIds, listOf(success.requestId.value, business.requestId.value))
        assertEquals(2, seenIds.toSet().size)
        assertEquals(RpcExecutionEvidence.HandlerFinished, success.executionEvidence)
        assertEquals(RpcExecutionEvidence.HandlerFinished, business.executionEvidence)
        assertFalse(success.toString().contains("private-response"))
        assertFalse(business.toString().contains("private-business-error"))
        assertEquals(2L, f.client.diagnostics.value.completedCalls)
        assertEquals(2L, f.client.requestTotals.value.accepted)
        assertEquals(1L, f.client.requestTotals.value.succeeded)
        assertEquals(1L, f.client.requestTotals.value.businessErrors)
        f.close()
    }

    @Test
    fun detailedReplyRecoveryKeepsTheWireIdAndIncludesRecoveryElapsedTime() = runTest {
        var executions = 0
        var handlerId: String? = null
        val f = fixture(registeredProcedure(procedure, { true }) { context, value ->
            executions++
            handlerId = context.requestId.value
            RpcReply.Success(value)
        })
        var loseFirst = true
        f.hostLink.onSend = {
            if (it.kind == WireKind.Success && loseFirst) loseFirst = false else f.client.onMessage(f.clientLink, it)
        }
        val observation = RpcCallObservation()
        val result = async {
            f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly(), observation)
        }
        runCurrent()
        val early = observation.progress.value
        assertEquals(handlerId, early.requestId)
        assertEquals(RpcCallStage.AwaitingResponse, early.stage)
        assertEquals(RpcExecutionEvidence.MayHaveExecuted, early.executionEvidence)
        advanceTimeBy(5_001); runCurrent()
        assertEquals(RpcCallStage.Succeeded, observation.progress.value.stage)
        assertEquals(early.requestId, observation.progress.value.requestId)
        assertEquals(5_000L, observation.progress.value.elapsedMillis)
        assertEquals(0, f.client.diagnostics.value.queuedCalls)
        val details = result.await()
        assertEquals(handlerId, details.requestId.value)
        assertEquals(5_000L, details.elapsedMillis)
        assertEquals(1, executions)
        assertEquals(listOf(WireKind.Invoke, WireKind.Status),
            f.clientLink.sent.map { it.kind }.filter { it == WireKind.Invoke || it == WireKind.Status })
        f.close()
    }

    @Test
    fun detailedCallFailureRetainsTheOriginalDeadlineAndAmbiguousExecutionEvidence() = runTest {
        val f = fixture(registeredProcedure(procedure, { true }) { _, value -> RpcReply.Success(value) })
        f.clientLink.onSend = {}
        val outcome = async {
            runCatching { f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) }
        }
        runCurrent(); advanceTimeBy(10_000); runCurrent()
        val failure = assertIs<RpcFailure>(outcome.await().exceptionOrNull())
        assertEquals(RpcFailureKind.DeadlineExceeded, failure.kind)
        assertEquals(RpcExecutionEvidence.MayHaveExecuted, failure.executionEvidence)
        assertEquals(f.clientLink.sent.first { it.kind == WireKind.Invoke }.id, failure.requestId?.value)
        assertEquals(1, f.clientLink.sent.count { it.kind == WireKind.Invoke })
        f.close()
    }

    @Test
    fun typedCallsCompleteOutOfOrderAndBusinessErrorsRemainTyped() = runTest {
        val firstGate = CompletableDeferred<Unit>()
        val descriptor = registeredProcedure(procedure, { true }) { _, value ->
            if (value == "one") firstGate.await()
            if (value == "error") RpcReply.ApplicationError("business-denial") else RpcReply.Success(value)
        }
        val f = fixture(descriptor)
        val first = async { f.client.call(procedure, "one", 10.seconds, RpcRetry.RecoverOnly()) }
        runCurrent()
        val second = async { f.client.call(procedure, "two", 10.seconds, RpcRetry.RecoverOnly()) }
        runCurrent()
        assertEquals("two", assertIs<RpcReply.Success<String>>(second.await()).value)
        assertFalse(first.isCompleted)
        firstGate.complete(Unit); runCurrent()
        assertEquals("one", assertIs<RpcReply.Success<String>>(first.await()).value)
        val business = f.client.call(procedure, "error", 10.seconds, RpcRetry.RecoverOnly())
        assertEquals("business-denial", assertIs<RpcReply.ApplicationError<String>>(business).error)
        f.close()
    }

    @Test
    fun lostResponseRecoversRetainedResultWithoutReinvokingHandler() = runTest {
        var executions = 0
        val f = fixture(registeredProcedure(procedure, { true }) { _, value -> executions++; RpcReply.Success(value) })
        var loseFirst = true
        f.hostLink.onSend = {
            if (it.kind == WireKind.Success && loseFirst) loseFirst = false else f.client.onMessage(f.clientLink, it)
        }
        val result = async { f.client.call(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) }
        runCurrent(); advanceTimeBy(5_001); runCurrent()
        assertEquals("q", assertIs<RpcReply.Success<String>>(result.await()).value)
        assertEquals(1, executions)
        assertEquals(listOf(WireKind.Invoke, WireKind.Status),
            f.clientLink.sent.map { it.kind }.filter { it == WireKind.Invoke || it == WireKind.Status })
        f.close()
    }

    @Test
    fun ambiguousInvocationWithNoRecordReportsUnknownAndNeverUnsafeReplay() = runTest {
        var executions = 0
        val f = fixture(registeredProcedure(procedure, { true }) { _, value -> executions++; RpcReply.Success(value) })
        f.clientLink.onSend = { if (it.kind != WireKind.Invoke) f.host.onMessage(f.hostLink, it) }
        val outcome = async { runCatching { f.client.call(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) } }
        runCurrent(); advanceTimeBy(5_001); runCurrent()
        val failure = assertIs<RpcFailure>(outcome.await().exceptionOrNull())
        assertEquals(RpcFailureKind.UnknownOutcome, failure.kind)
        assertEquals(RpcExecutionEvidence.MayHaveExecuted, failure.executionEvidence)
        assertEquals(0, executions)
        assertEquals(1, f.clientLink.sent.count { it.kind == WireKind.Invoke })
        f.close()
    }

    @Test
    fun idempotentReinvocationRequiresBothOptInsAndKeepsIdAndBytes() = runTest {
        val idempotent = RpcProcedure("echo", 1, String.serializer(), String.serializer(), String.serializer(),
            retrySafety = RpcRetrySafety.Idempotent)
        var executions = 0
        val f = fixture(registeredProcedure(idempotent, { true }) { _, value -> executions++; RpcReply.Success(value) })
        var loseFirst = true
        f.clientLink.onSend = {
            if (it.kind == WireKind.Invoke && loseFirst) loseFirst = false else f.host.onMessage(f.hostLink, it)
        }
        val result = async { f.client.call(idempotent, "frozen", 10.seconds, RpcRetry.Idempotent()) }
        runCurrent(); advanceTimeBy(5_001); runCurrent()
        assertEquals("frozen", assertIs<RpcReply.Success<String>>(result.await()).value)
        val invocations = f.clientLink.sent.filter { it.kind == WireKind.Invoke }
        assertEquals(2, invocations.size)
        assertEquals(invocations[0].id, invocations[1].id)
        assertTrue(invocations[0].body!!.bytes.contentEquals(invocations[1].body!!.bytes))
        assertEquals(1, invocations[1].code)
        assertEquals(1, executions)
        assertFailsWith<IllegalArgumentException> {
            f.client.call(procedure, "unsafe", 10.seconds, RpcRetry.Idempotent())
        }
        f.close()
    }

    @Test
    fun cancellationBeforeQueueStartNeverTransmitsAndDeadlineDoesNotResetAcrossRecovery() = runTest {
        val f = fixture(registeredProcedure(procedure, { true }) { _, value -> RpcReply.Success(value) })
        f.clientLink.paused = true
        val observation = RpcCallObservation()
        val cancelled = async {
            f.client.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly(), observation)
        }
        runCurrent()
        assertEquals(RpcCallStage.Queued, observation.progress.value.stage)
        assertEquals(1, f.client.diagnostics.value.queuedCalls)
        assertEquals(RpcExecutionEvidence.NotSent, observation.progress.value.executionEvidence)
        assertTrue(observation.progress.value.requestId != null)
        cancelled.cancel(); runCurrent()
        assertEquals(RpcCallStage.Cancelled, observation.progress.value.stage)
        assertEquals(0, f.client.diagnostics.value.queuedCalls)
        assertEquals(RpcExecutionEvidence.NotSent, observation.progress.value.executionEvidence)
        f.clientLink.queued.toList().forEach { f.clientLink.deliver(it) }
        assertEquals(0, f.clientLink.sent.count { it.kind == WireKind.Invoke })
        assertEquals(1L, f.client.requestTotals.value.cancelled)
        f.clientLink.paused = false
        f.clientLink.onSend = {} // local sends succeed, every remote response/status is lost
        val startedAt = testScheduler.currentTime
        val outcome = async { runCatching { f.client.call(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) } }
        runCurrent(); advanceTimeBy(10_000); runCurrent()
        val failure = assertIs<RpcFailure>(outcome.await().exceptionOrNull())
        assertEquals(RpcFailureKind.DeadlineExceeded, failure.kind)
        assertEquals(10_000L, testScheduler.currentTime - startedAt)
        assertEquals(1L, f.client.requestTotals.value.timedOut)
        assertTrue(f.clientLink.sent.count { it.kind == WireKind.Invoke || it.kind == WireKind.Status } <= 3)
        f.close()
    }

    @Test
    fun hostRestartBlocksReplayEvenForIdempotentCalls() = runTest {
        val idempotent = RpcProcedure("echo", 1, String.serializer(), String.serializer(), String.serializer(),
            retrySafety = RpcRetrySafety.Idempotent)
        val f = fixture(registeredProcedure(idempotent, { true }) { _, value -> RpcReply.Success(value) })
        // Lose invocation, then replace the underlying authenticated generation/host incarnation.
        f.clientLink.onSend = { message ->
            if (message.kind == WireKind.Hello) f.client.onMessage(f.clientLink, WireMessage(
                WireKind.Ready, message.id, "44444444444444444444444444444444", code = 1))
        }
        val result = async { runCatching { f.client.call(idempotent, "q", 10.seconds, RpcRetry.Idempotent()) } }
        runCurrent()
        f.clientLink.transportState.value = ConnectionState.Reconnecting
        runCurrent()
        f.clientLink.generation.value = SessionConnectionInfo(2)
        f.clientLink.transportState.value = ConnectionState.Connected
        runCurrent(); advanceTimeBy(5_001); runCurrent()
        assertEquals(RpcFailureKind.HostRestarted, assertIs<RpcFailure>(result.await().exceptionOrNull()).kind)
        assertEquals(1, f.clientLink.sent.count { it.kind == WireKind.Invoke })
        f.close()
    }

    @Test
    fun missingReadyIsRetriedAndAStaleReadyCannotAuthorizeAnotherGeneration() = runTest {
        val budget = PayloadBudget(4096)
        val client = RpcClientEngine(backgroundScope, budget, RpcClock { testScheduler.currentTime })
        val link = RpcTestLink()
        var first: WireMessage? = null
        link.onSend = { message ->
            if (first == null) first = message.copy() else client.onMessage(
                link, WireMessage(WireKind.Ready, message.id, TEST_INCARNATION, code = 1),
            )
        }
        client.attach(link)
        runCurrent()
        assertNull(client.ready.value)
        advanceTimeBy(250)
        runCurrent()
        assertEquals(TEST_INCARNATION, client.awaitReady().incarnation)
        link.onSend = {}
        link.generation.value = SessionConnectionInfo(2)
        runCurrent()
        assertNull(client.ready.value)
        client.onMessage(link, WireMessage(WireKind.Ready, checkNotNull(first).id, TEST_INCARNATION, code = 1))
        assertNull(client.ready.value)
        client.close()
        link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun callsFailLocallyAtDisconnectOrUnobservedGenerationChange() = runTest {
        val f = fixture(registeredProcedure(procedure, { true }) { _, value -> RpcReply.Success(value) })
        // Intentionally do not dispatch the negotiation monitor before making the new call.
        f.clientLink.transportState.value = ConnectionState.Reconnecting
        assertEquals(RpcFailureKind.NotConnected, assertFailsWith<RpcFailure> {
            f.client.call(procedure, "must not queue", 10.seconds, RpcRetry.RecoverOnly())
        }.kind)
        f.clientLink.generation.value = SessionConnectionInfo(2)
        f.clientLink.transportState.value = ConnectionState.Connected
        assertEquals(RpcFailureKind.NotConnected, assertFailsWith<RpcFailure> {
            f.client.call(procedure, "must negotiate first", 10.seconds, RpcRetry.RecoverOnly())
        }.kind)
        assertEquals(0, f.clientLink.sent.count { it.kind == WireKind.Invoke })
        f.close()
    }

    @Test
    fun replacingSelectedHostNeverLeaksOldCallControlsOrCancelsNewNegotiation() = runTest {
        val f = fixture(registeredProcedure(procedure, { true }) { _, value -> RpcReply.Success(value) })
        f.clientLink.onSend = {}
        val oldCall = async { runCatching { f.client.call(procedure, "old", 10.seconds, RpcRetry.RecoverOnly()) } }
        runCurrent()
        f.client.detach(f.clientLink)
        val replacement = RpcTestLink(2)
        replacement.onSend = { message ->
            if (message.kind == WireKind.Hello) f.client.onMessage(
                replacement, WireMessage(WireKind.Ready, message.id, TEST_SECOND, code = 1),
            )
        }
        f.client.attach(replacement)
        runCurrent()
        assertIs<RpcFailure>(oldCall.await().exceptionOrNull())
        assertEquals(TEST_SECOND, f.client.awaitReady().incarnation)
        assertTrue(f.clientLink.sent.any { it.kind == WireKind.Cancel })
        assertTrue(replacement.sent.all { it.kind == WireKind.Hello })
        f.client.detach(f.clientLink) // Late old onClosed callback is harmless.
        assertEquals(TEST_SECOND, f.client.awaitReady().incarnation)
        f.close()
        replacement.clearSent()
    }

    @Test
    fun clientOutstandingLimitFailsBeforeEncodingOrSendingAnotherCall() = runTest {
        val gate = CompletableDeferred<Unit>()
        val f = fixture(registeredProcedure(procedure, { true }) { _, value -> gate.await(); RpcReply.Success(value) })
        val calls = List(8) { async { f.client.call(procedure, "q", 10.seconds, RpcRetry.RecoverOnly()) } }
        runCurrent()
        val failure = assertFailsWith<RpcFailure> {
            f.client.call(procedure, "excess", 10.seconds, RpcRetry.RecoverOnly())
        }
        assertEquals(RpcFailureKind.Overloaded, failure.kind)
        assertEquals(RpcExecutionEvidence.NotSent, failure.executionEvidence)
        assertEquals(8, f.clientLink.sent.count { it.kind == WireKind.Invoke })
        assertEquals(8L, f.client.requestTotals.value.accepted)
        assertEquals(1L, f.client.requestTotals.value.refusedAttempts)
        gate.complete(Unit)
        calls.forEach { assertIs<RpcReply.Success<String>>(it.await()) }
        f.close()
    }

    @Test
    fun malformedResultKeepsDecodingPhaseAndHandlerFinishedEvidence() = runTest {
        val f = fixture(registeredProcedure(procedure, { true }) { _, value -> RpcReply.Success(value) })
        f.hostLink.onSend = { message ->
            if (message.kind == WireKind.Success) {
                val malformed = message.copy(body = testBody("not-json", f.budget))
                try { f.client.onMessage(f.clientLink, malformed) } finally { malformed.release() }
            } else f.client.onMessage(f.clientLink, message)
        }
        val failure = assertFailsWith<RpcFailure> {
            f.client.call(procedure, "q", 10.seconds, RpcRetry.RecoverOnly())
        }
        assertEquals(RpcFailureKind.InvalidPayload, failure.kind)
        assertEquals(RpcFailurePhase.Decoding, failure.phase)
        assertEquals(1L, f.client.requestTotals.value.failed)
        assertEquals(0L, f.client.requestTotals.value.succeeded)
        assertEquals(RpcExecutionEvidence.HandlerFinished, failure.executionEvidence)
        assertTrue(failure.requestId != null)
        assertEquals(1, f.clientLink.sent.count { it.kind == WireKind.Invoke })
        f.close()
    }
}
