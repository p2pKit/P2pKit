package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PeerAdmission
import dev.p2pkit.core.security.payloadSha256
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.serialization.builtins.serializer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class RpcHostEngineTest {
    private val procedure = RpcProcedure("echo", 1, String.serializer(), String.serializer(), String.serializer())
    private fun invoke(budget: PayloadBudget, id: String = TEST_REQUEST, body: String = "q") = WireMessage(
        WireKind.Invoke, id, TEST_INCARNATION, "echo", 1, 10_000, 1, body = testBody("\"$body\"", budget)
    )
    private fun control(budget: PayloadBudget, kind: WireKind, id: String = TEST_REQUEST) = WireMessage(
        kind, id, TEST_INCARNATION, "echo", 1, attempt = if (kind == WireKind.Status) 2 else 0,
        body = OwnedBytes.copy(payloadSha256("\"q\"".encodeToByteArray()), budget)
    )

    @Test
    fun observedQueueCancellationAndDuplicateRecoveryKeepExactLogicalTotals() = runTest {
        val budget = PayloadBudget(8L * 1_048_576)
        val gate = CompletableDeferred<Unit>()
        val descriptor = registeredProcedure(procedure, { true }) { context, value ->
            assertEquals(TEST_INCARNATION, context.hostIncarnation)
            gate.await()
            RpcReply.Success(value)
        }
        val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor),
            RpcLimits(runningCalls = 1), budget, RpcClock { testScheduler.currentTime }, { true },
            TEST_INCARNATION, requestHistoryCapacity = 4)
        val link = RpcTestLink(); host.negotiate(link)
        val second = TEST_SECOND
        host.deliver(link, invoke(budget)); runCurrent()
        host.deliver(link, invoke(budget, second)); runCurrent()
        assertEquals(listOf(dev.p2pkit.rpc.RpcHostCallState.Running, dev.p2pkit.rpc.RpcHostCallState.Queued),
            host.requests.value.entries.map { it.state })
        host.deliver(link, control(budget, WireKind.Cancel, second)); runCurrent()
        val cancelled = host.requests.value.entries.last()
        assertEquals(dev.p2pkit.rpc.RpcHostCallState.Cancelled, cancelled.state)
        assertEquals(dev.p2pkit.rpc.RpcExecutionEvidence.RejectedBeforeExecution, cancelled.executionEvidence)
        gate.complete(Unit); runCurrent()
        host.deliver(link, invoke(budget)); runCurrent()
        assertEquals(2L, host.requests.value.totals.accepted)
        assertEquals(1L, host.requests.value.totals.succeeded)
        assertEquals(1L, host.requests.value.totals.cancelled)
        assertEquals(2, host.requests.value.entries.size)
        host.close(); link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun observedUnknownProcedureIsARefusedAttemptNotAnAdmittedExecution() = runTest {
        val budget = PayloadBudget(1_048_576)
        val host = RpcHostEngine(backgroundScope, emptyMap(), RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION, requestHistoryCapacity = 2)
        val link = RpcTestLink(); host.negotiate(link)
        host.deliver(link, invoke(budget)); runCurrent()
        assertEquals(0L, host.requests.value.totals.accepted)
        assertEquals(1L, host.requests.value.totals.refusedAttempts)
        assertEquals(dev.p2pkit.rpc.RpcHostCallState.Refused, host.requests.value.entries.single().state)
        assertEquals(dev.p2pkit.rpc.RpcFailureKind.UnknownProcedure, host.requests.value.entries.single().failure)
        host.close(); link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun observedQueuedDeadlineCannotBeMisreportedAsHandlerExecution() = runTest {
        val budget = PayloadBudget(8L * 1_048_576)
        val gate = CompletableDeferred<Unit>()
        var executions = 0
        val descriptor = registeredProcedure(procedure, { true }) { _, value ->
            executions++
            gate.await()
            RpcReply.ApplicationError(value)
        }
        val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor),
            RpcLimits(runningCalls = 1), budget, RpcClock { testScheduler.currentTime }, { true },
            TEST_INCARNATION, requestHistoryCapacity = 4)
        val link = RpcTestLink(); host.negotiate(link)
        host.deliver(link, invoke(budget)); runCurrent()
        val second = TEST_SECOND
        host.deliver(link, invoke(budget, second).copy(budgetMillis = 1)); runCurrent()
        advanceTimeBy(2); host.sweep(); runCurrent()
        assertEquals(dev.p2pkit.rpc.RpcHostCallState.TimedOut, host.requests.value.entries.last().state)
        assertEquals(dev.p2pkit.rpc.RpcExecutionEvidence.RejectedBeforeExecution,
            host.requests.value.entries.last().executionEvidence)
        gate.complete(Unit); runCurrent()
        assertEquals(1, executions)
        assertEquals(1L, host.requests.value.totals.timedOut)
        assertEquals(1L, host.requests.value.totals.businessErrors)
        host.close(); link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun concurrentDuplicatesJoinAndCompletedDuplicatesReuseOneExecution() = runTest {
        val budget = PayloadBudget(8L * 1_048_576)
        val gate = CompletableDeferred<Unit>()
        var executions = 0
        val descriptor = registeredProcedure(procedure, { true }) { _, value ->
            executions++; gate.await(); RpcReply.Success(value)
        }
        val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION)
        val link = RpcTestLink()
        host.negotiate(link)
        host.deliver(link, invoke(budget))
        runCurrent()
        host.deliver(link, invoke(budget))
        assertEquals(1, executions)
        assertEquals(WireKind.Running, link.sent.last().kind)
        gate.complete(Unit)
        runCurrent()
        assertEquals(WireKind.Success, link.sent.last().kind)
        host.deliver(link, invoke(budget))
        assertEquals(WireKind.Success, link.sent.last().kind)
        assertEquals(1, executions)
        host.close(); link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun alteredPayloadReuseIsAProtocolViolationNotAnotherExecution() = runTest {
        val budget = PayloadBudget(4L * 1_048_576)
        var executions = 0
        val descriptor = registeredProcedure(procedure, { true }) { _, value -> executions++; RpcReply.Success(value) }
        val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION)
        val link = RpcTestLink(); host.negotiate(link)
        host.deliver(link, invoke(budget)); runCurrent()
        assertFailsWith<RpcFailure> { host.deliver(link, invoke(budget, body = "changed")) }
        assertEquals(1, executions)
        host.close(); link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun receiptsAndCachePressureKeepTombstonesAndDoNotPermitReexecution() = runTest {
        for (cache in listOf(0L, 1_048_576L)) {
            val budget = PayloadBudget(8L * 1_048_576)
            var executions = 0
            val descriptor = registeredProcedure(procedure, { true }) { _, value ->
                executions++
                RpcReply.Success(value)
            }
            val host = RpcHostEngine(
                backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(resultCacheBytes = cache),
                budget, RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION,
            )
            val link = RpcTestLink(); host.negotiate(link)
            host.deliver(link, invoke(budget)); runCurrent()
            assertEquals(WireKind.Success, link.sent.last().kind)
            host.deliver(link, control(budget, WireKind.Receipt))
            host.deliver(link, invoke(budget))
            assertEquals(WireFailure.ResultUnavailable.code, link.sent.last().code)
            assertEquals(1, executions)
            advanceTimeBy(60_001); host.sweep()
            host.deliver(link, control(budget, WireKind.Status))
            assertEquals(WireFailure.UnknownOutcome.code, link.sent.last().code)
            assertEquals(1, executions) // Expiry does not cause an invocation.
            host.close(); link.clearSent()
            assertEquals(0L, budget.retainedBytes.value)
        }
    }

    @Test
    fun nonCooperativeHandlersKeepTheirSlotAndRunningRecordsPastRetentionWindow() = runTest {
        val budget = PayloadBudget(8L * 1_048_576)
        val gate = CompletableDeferred<Unit>()
        val descriptor = registeredProcedure(procedure, { true }) { _, value ->
            withContext(NonCancellable) { gate.await() }; RpcReply.Success(value)
        }
        val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor),
            RpcLimits(runningCalls = 1, queuedCalls = 0), budget, RpcClock { testScheduler.currentTime },
            { true }, TEST_INCARNATION)
        val link = RpcTestLink(); host.negotiate(link)
        host.deliver(link, invoke(budget)); runCurrent()
        advanceTimeBy(61_000); runCurrent(); host.sweep()
        host.deliver(link, invoke(budget))
        assertEquals(WireKind.Running, link.sent.last().kind)
        host.deliver(link, invoke(budget, TEST_SECOND))
        assertEquals(WireFailure.Overloaded.code, link.sent.last().code)
        assertEquals(1, host.diagnostics.value.runningCalls)
        gate.complete(Unit); runCurrent()
        assertEquals(0, host.diagnostics.value.runningCalls)
        assertEquals(WireFailure.Deadline.code, link.sent.last().code)
        host.close(); link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun queuedCancellationAndAuthorizationRefusalNeverStartHandlers() = runTest {
        val budget = PayloadBudget(8L * 1_048_576)
        val gate = CompletableDeferred<Unit>()
        var allow = true
        var executions = 0
        val descriptor = registeredProcedure(procedure, { allow }) { _, value ->
            executions++
            gate.await()
            RpcReply.Success(value)
        }
        val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor),
            RpcLimits(runningCalls = 1, queuedCalls = 1), budget, RpcClock { testScheduler.currentTime },
            { true }, TEST_INCARNATION)
        val link = RpcTestLink(); host.negotiate(link)
        host.deliver(link, invoke(budget)); runCurrent()
        host.deliver(link, invoke(budget, TEST_SECOND))
        host.deliver(link, control(budget, WireKind.Cancel, TEST_SECOND))
        assertEquals(WireFailure.CancelledBeforeStart.code, link.sent.last().code)
        allow = false
        host.deliver(link, control(budget, WireKind.Status))
        assertEquals(WireFailure.AccessRevoked.code, link.sent.last().code)
        assertEquals(1, executions)
        gate.complete(Unit); runCurrent()
        host.close(); link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun recordLimitsRefuseBeforeExecutionAndRestartNeverReplaysOldIncarnations() = runTest {
        val budget = PayloadBudget(4L * 1_048_576)
        var executions = 0
        val descriptor = registeredProcedure(procedure, { true }) { _, value -> executions++; RpcReply.Success(value) }
        val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor),
            RpcLimits(recordsPerClient = 1, totalRecords = 1), budget, RpcClock { testScheduler.currentTime },
            { true }, TEST_INCARNATION)
        val link = RpcTestLink(); host.negotiate(link)
        host.deliver(link, invoke(budget)); runCurrent()
        host.deliver(link, invoke(budget, TEST_SECOND))
        assertEquals(WireFailure.Overloaded.code, link.sent.last().code)
        assertEquals(1, executions)
        host.close(); link.clearSent()
        val restarted = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, "44444444444444444444444444444444")
        val fresh = RpcTestLink(); restarted.negotiate(fresh)
        restarted.deliver(fresh, invoke(budget))
        assertEquals(WireFailure.HostRestarted.code, fresh.sent.last().code)
        assertTrue(restarted.diagnostics.value.retainedRecords == 0)
        restarted.close(); fresh.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun approvalCannotUpgradeAnEnrollmentConnectionOrExposeACachedResult() = runTest {
        val budget = PayloadBudget(4L * 1_048_576)
        var executions = 0
        val descriptor = registeredProcedure(procedure, { true }) { _, value ->
            executions++
            RpcReply.Success(value)
        }
        val host = RpcHostEngine(
            backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION,
        )
        val quarantined = RpcTestLink(admission = PeerAdmission.EnrollmentOnly)
        host.negotiate(quarantined)
        host.deliver(quarantined, invoke(budget))
        runCurrent()
        assertEquals(0, executions) // Trust is already approved, but the captured admission is not.
        val fresh = RpcTestLink()
        host.negotiate(fresh)
        host.deliver(fresh, invoke(budget))
        runCurrent()
        assertEquals(1, executions)
        val stillQuarantined = RpcTestLink(admission = PeerAdmission.EnrollmentOnly)
        host.negotiate(stillQuarantined)
        host.deliver(stillQuarantined, control(budget, WireKind.Status))
        assertTrue(stillQuarantined.sent.none { it.kind == WireKind.Success })
        host.close()
        fresh.clearSent()
        quarantined.clearSent()
        stillQuarantined.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun returningCachedResultsRechecksAuthorizationAndLiveRevocation() = runTest {
        val budget = PayloadBudget(4L * 1_048_576)
        var authorized = true
        var trusted = true
        val descriptor = registeredProcedure(procedure, { authorized }) { _, value -> RpcReply.Success(value) }
        val host = RpcHostEngine(
            backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { trusted }, TEST_INCARNATION,
        )
        val link = RpcTestLink()
        host.negotiate(link)
        host.deliver(link, invoke(budget))
        runCurrent()
        authorized = false
        host.deliver(link, control(budget, WireKind.Status))
        assertEquals(WireFailure.AccessRevoked.code, link.sent.last().code)
        assertEquals(null, link.sent.last().body)
        trusted = false
        host.revoke(testFingerprint())
        authorized = true
        val fresh = RpcTestLink()
        host.negotiate(fresh)
        assertEquals(dev.p2pkit.core.ConnectionState.Closed, fresh.transportState.value)
        host.close()
        link.clearSent()
        fresh.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun queuedDeadlineDoesNotBorrowARunningSlotAndDuplicatesCannotExtendIt() = runTest {
        val budget = PayloadBudget(8L * 1_048_576)
        val gate = CompletableDeferred<Unit>()
        var executions = 0
        val descriptor = registeredProcedure(procedure, { true }) { _, value ->
            executions++
            gate.await()
            RpcReply.Success(value)
        }
        val host = RpcHostEngine(
            backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(runningCalls = 1, queuedCalls = 1),
            budget, RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION,
        )
        val link = RpcTestLink()
        host.negotiate(link)
        host.deliver(link, invoke(budget))
        runCurrent()
        host.deliver(link, invoke(budget, TEST_SECOND).copy(budgetMillis = 100))
        advanceTimeBy(251)
        runCurrent()
        assertEquals(WireFailure.DeadlineBeforeStart.code, link.sent.last().code)
        host.deliver(link, invoke(budget, TEST_SECOND).copy(budgetMillis = 30_000))
        assertEquals(WireFailure.DeadlineBeforeStart.code, link.sent.last().code)
        assertEquals(1, executions)
        assertEquals(1, host.diagnostics.value.runningCalls)
        assertEquals(0, host.diagnostics.value.queuedCalls)
        gate.complete(Unit)
        runCurrent()
        host.close()
        link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun cancellingARunningHandlerDoesNotUndoItsSideEffectOrPermitDuplicateExecution() = runTest {
        val budget = PayloadBudget(4L * 1_048_576)
        val neverFinishes = CompletableDeferred<Unit>()
        var sideEffects = 0
        val descriptor = registeredProcedure(procedure, { true }) { _, value ->
            sideEffects++
            neverFinishes.await()
            RpcReply.Success(value)
        }
        val host = RpcHostEngine(
            backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION,
        )
        val link = RpcTestLink()
        host.negotiate(link)
        host.deliver(link, invoke(budget))
        runCurrent()
        assertEquals(1, sideEffects)
        host.deliver(link, control(budget, WireKind.Cancel))
        runCurrent()
        assertEquals(WireFailure.Cancelled.code, link.sent.last().code)
        assertEquals(0, host.diagnostics.value.runningCalls)
        host.deliver(link, invoke(budget))
        assertEquals(WireFailure.Cancelled.code, link.sent.last().code)
        assertEquals(1, sideEffects)
        host.close()
        link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun queuedDuplicatesShareTheSinglePromotionOwner() = runTest {
        val budget = PayloadBudget(8L * 1_048_576)
        val first = CompletableDeferred<Unit>()
        val executedIds = mutableListOf<String>()
        val descriptor = registeredProcedure(procedure, { true }) { context, value ->
            executedIds += context.requestId.value
            if (context.requestId.value == TEST_REQUEST) first.await()
            RpcReply.Success(value)
        }
        val host = RpcHostEngine(
            backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(runningCalls = 1, queuedCalls = 1),
            budget, RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION,
        )
        val link = RpcTestLink()
        host.negotiate(link)
        host.deliver(link, invoke(budget))
        runCurrent()
        host.deliver(link, invoke(budget, TEST_SECOND))
        host.deliver(link, invoke(budget, TEST_SECOND))
        assertEquals(WireKind.Running, link.sent.last().kind)
        first.complete(Unit)
        runCurrent()
        assertEquals(listOf(TEST_REQUEST, TEST_SECOND), executedIds)
        assertEquals(2L, host.diagnostics.value.completedCalls)
        assertEquals(0, host.diagnostics.value.queuedCalls)
        host.close()
        link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun admissionAuthorizationCannotExtendTheAdvertisedRequestDeadline() = runTest {
        val budget = PayloadBudget(4L * 1_048_576)
        var executions = 0
        val descriptor = registeredProcedure(procedure, { awaitCancellation() }) { _, value ->
            executions++
            RpcReply.Success(value)
        }
        val host = RpcHostEngine(
            backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION,
        )
        val link = RpcTestLink()
        host.negotiate(link)
        val delivery = async { host.deliver(link, invoke(budget).copy(budgetMillis = 25)) }
        runCurrent()
        advanceTimeBy(25)
        runCurrent()
        delivery.await()
        assertEquals(WireFailure.DeadlineBeforeStart.code, link.sent.last().code)
        assertEquals(0, executions)
        assertEquals(0, host.diagnostics.value.retainedRecords)
        host.close()
        link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun resultAuthorizationTimeoutReleasesExecutionSlotButKeepsRecoverableOutcome() = runTest {
        val budget = PayloadBudget(4L * 1_048_576)
        var checks = 0
        var allowResults = false
        var executions = 0
        val descriptor = registeredProcedure(procedure, {
            checks++
            if (checks == 1 || allowResults) true else awaitCancellation()
        }) { _, value ->
            executions++
            RpcReply.Success(value)
        }
        val host = RpcHostEngine(
            backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(runningCalls = 1), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION,
        )
        val link = RpcTestLink()
        host.negotiate(link)
        host.deliver(link, invoke(budget))
        runCurrent()
        assertEquals(1, host.diagnostics.value.runningCalls)
        advanceTimeBy(5_000)
        runCurrent()
        assertEquals(0, host.diagnostics.value.runningCalls)
        assertEquals(1, host.diagnostics.value.retainedRecords)
        assertTrue(link.sent.none { it.kind == WireKind.Success })
        allowResults = true
        host.deliver(link, control(budget, WireKind.Status))
        assertEquals(WireKind.Success, link.sent.last().kind)
        assertEquals(1, executions)
        host.close()
        link.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun replacementRequiresItsOwnHelloAndOldTrafficCannotAuthorizeOrDetachIt() = runTest {
        val budget = PayloadBudget(4L * 1_048_576)
        var executions = 0
        val descriptor = registeredProcedure(procedure, { true }) { _, value ->
            executions++
            RpcReply.Success(value)
        }
        val host = RpcHostEngine(
            backgroundScope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION,
        )
        val old = RpcTestLink()
        host.negotiate(old)
        val replacement = RpcTestLink()
        host.attach(replacement)
        assertNull(host.trustedLink(testFingerprint()))
        host.onMessage(old, WireMessage(WireKind.Hello, TEST_REQUEST))
        assertNull(host.trustedLink(testFingerprint()))
        assertFailsWith<RpcFailure> { host.deliver(old, invoke(budget)) }
        assertEquals(0, executions)
        host.onMessage(replacement, WireMessage(WireKind.Hello, TEST_SECOND))
        assertSame(replacement, host.trustedLink(testFingerprint()))
        host.detach(old)
        assertSame(replacement, host.trustedLink(testFingerprint()))
        host.deliver(replacement, invoke(budget))
        runCurrent()
        assertEquals(1, executions)
        assertEquals(WireKind.Success, replacement.sent.last().kind)
        host.close()
        old.clearSent()
        replacement.clearSent()
        assertEquals(0L, budget.retainedBytes.value)
    }
}
