package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.encoding.Encoder
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class RpcHostFailureOwnershipTest {
    private val procedure = RpcProcedure("echo", 1, String.serializer(), String.serializer(), String.serializer())

    // Retain an owned field so stacktrace recovery cannot copy this application Error.
    private class ReportingError(message: String) : Error(message) {
        val owner = Any()
    }

    private class Fixture(
        val budget: PayloadBudget,
        val host: RpcHostEngine,
        val owner: Job,
        val errors: MutableList<Throwable>,
    ) {
        suspend fun close(vararg links: RpcTestLink) {
            try {
                host.close()
            } finally {
                owner.cancelAndJoin()
                links.forEach { it.close(); it.clearSent() }
            }
            assertEquals(0, host.diagnostics.value.runningCalls)
            assertEquals(0, host.diagnostics.value.queuedCalls)
            assertEquals(0, host.diagnostics.value.retainedRecords)
            assertEquals(0L, budget.retainedBytes.value)
        }
    }

    private fun TestScope.fixture(descriptor: RegisteredProcedure): Fixture {
        val budget = PayloadBudget(4L * 1_048_576)
        val errors = mutableListOf<Throwable>()
        val owner = SupervisorJob()
        val scope = CoroutineScope(coroutineContext + owner + CoroutineExceptionHandler { _, failure ->
            errors += failure
        })
        val host = RpcHostEngine(scope, mapOf(descriptor.key to descriptor),
            RpcLimits(runningCalls = 1, queuedCalls = 2), budget, RpcClock { testScheduler.currentTime },
            { true }, TEST_INCARNATION)
        return Fixture(budget, host, owner, errors)
    }

    private fun invoke(id: String, value: String, budget: PayloadBudget): WireMessage = WireMessage(
        WireKind.Invoke, id, TEST_INCARNATION, procedure.name, procedure.version, 10_000, 1,
        body = testBody("\"$value\"", budget),
    )

    private fun assertOriginalError(expected: ReportingError, observed: Throwable) {
        assertIs<ReportingError>(observed)
        assertSame(expected, observed)
    }

    @Test
    fun resultAuthorizerErrorFinishesOwnershipAndRunsQueuedWorkWithoutDeliveringDeniedResult() = runTest {
        val marker = ReportingError("Result authorization fixture failure")
        val first = RpcTestLink()
        val second = RpcTestLink(1)
        var firstChecks = 0
        var executions = 0
        val f = fixture(registeredProcedure(procedure, { identity ->
            if (identity.fingerprint == first.identity.fingerprint && ++firstChecks == 2) throw marker
            true
        }) { _, value ->
            executions++
            RpcReply.Success(value)
        })
        try {
            f.host.negotiate(first)
            f.host.negotiate(second)
            f.host.deliver(first, invoke(TEST_REQUEST, "first", f.budget))
            f.host.deliver(second, invoke(TEST_SECOND, "second", f.budget))
            assertEquals(1, f.host.diagnostics.value.runningCalls)
            assertEquals(1, f.host.diagnostics.value.queuedCalls)
            runCurrent()
            assertOriginalError(marker, f.errors.single())
            assertEquals(2, executions)
            assertEquals(2, firstChecks)
            assertTrue(first.sent.isEmpty(), "An authorization Error must not deliver the result")
            assertEquals(WireKind.Success, second.sent.single().kind)
            assertEquals(0, f.host.diagnostics.value.runningCalls)
            assertEquals(0, f.host.diagnostics.value.queuedCalls)
            assertEquals(2L, f.host.diagnostics.value.completedCalls)
            assertEquals(2, f.host.diagnostics.value.retainedRecords)
        } finally {
            f.close(first, second)
        }
    }

    @Test
    fun handlerAndResultAuthorizationErrorsKeepTheOriginalHandlerErrorAndReleaseTheirOwnership() = runTest {
        val handlerError = ReportingError("Handler fixture failure")
        val authorizationError = ReportingError("Result authorization fixture failure")
        val link = RpcTestLink()
        var checks = 0
        var executions = 0
        val f = fixture(registeredProcedure(procedure, {
            if (++checks == 2) throw authorizationError
            true
        }) { _, _ ->
            executions++
            throw handlerError
        })
        try {
            f.host.negotiate(link)
            f.host.deliver(link, invoke(TEST_REQUEST, "fixture", f.budget))
            runCurrent()
            val observed = f.errors.single()
            assertOriginalError(handlerError, observed)
            assertSame(authorizationError, observed.suppressedExceptions.single())
            assertEquals(1, executions)
            assertEquals(2, checks)
            assertTrue(link.sent.isEmpty())
            assertEquals(0, f.host.diagnostics.value.runningCalls)
            assertEquals(0, f.host.diagnostics.value.queuedCalls)
            assertEquals(1L, f.host.diagnostics.value.completedCalls)
            assertEquals(1, f.host.diagnostics.value.retainedRecords)
            assertEquals(0L, f.budget.retainedBytes.value)
        } finally {
            f.close(link)
        }
    }

    @Test
    fun resultSerializerErrorCompletesTheHandlerRecordAndReleasesItsEncodingLease() = runTest {
        val marker = ReportingError("Result serializer fixture failure")
        val serializer = object : KSerializer<String> by String.serializer() {
            override fun serialize(encoder: Encoder, value: String) {
                encoder.encodeString(value)
                throw marker
            }
        }
        val descriptor = RpcProcedure(procedure.name, 1, String.serializer(), serializer, String.serializer())
        val f = fixture(registeredProcedure(descriptor, { true }) { _, value -> RpcReply.Success(value) })
        val link = RpcTestLink()
        try {
            f.host.negotiate(link)
            f.host.deliver(link, invoke(TEST_REQUEST, "fixture", f.budget))
            runCurrent()
            assertOriginalError(marker, f.errors.single())
            assertEquals(WireKind.Failure, link.sent.single().kind)
            assertEquals(WireFailure.HandlerFailed.code, link.sent.single().code)
            assertEquals(0, f.host.diagnostics.value.runningCalls)
            assertEquals(1L, f.host.diagnostics.value.completedCalls)
            assertEquals(1, f.host.diagnostics.value.retainedRecords)
            assertEquals(0L, f.budget.retainedBytes.value)
        } finally {
            f.close(link)
        }
    }

    @Test
    fun closeRetainsAnUnfinishedResultAuthorizerThenReleasesEverythingWhenItsErrorReturns() = runTest {
        val marker = ReportingError("Result authorization fixture failure")
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        var checks = 0
        val f = fixture(registeredProcedure(procedure, {
            if (++checks == 2) {
                entered.complete(Unit)
                release.await()
                throw marker
            }
            true
        }) { _, value -> RpcReply.Success(value) })
        val link = RpcTestLink()
        try {
            f.host.negotiate(link)
            f.host.deliver(link, invoke(TEST_REQUEST, "fixture", f.budget))
            runCurrent()
            assertTrue(entered.isCompleted)
            f.host.close()
            assertEquals(1, f.host.diagnostics.value.runningCalls)
            assertEquals(1, f.host.diagnostics.value.retainedRecords)
            assertTrue(f.budget.retainedBytes.value > 0)
            assertTrue(f.errors.isEmpty())
            release.complete(Unit)
            runCurrent()
            assertOriginalError(marker, f.errors.single())
            assertTrue(link.sent.isEmpty())
            assertEquals(0, f.host.diagnostics.value.runningCalls)
            assertEquals(0, f.host.diagnostics.value.retainedRecords)
            assertEquals(0L, f.budget.retainedBytes.value)
            assertEquals(0L, f.host.diagnostics.value.retainedPayloadBytes)
        } finally {
            release.complete(Unit)
            f.close(link)
        }
    }
}
