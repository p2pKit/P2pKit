package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.security.payloadSha256
import dev.p2pkit.rpc.RpcApplicationSession
import dev.p2pkit.rpc.RpcAuthorizationContext
import dev.p2pkit.rpc.RpcAuthorizationOperation
import dev.p2pkit.rpc.RpcAuthorizationScope
import dev.p2pkit.rpc.RpcCallContext
import dev.p2pkit.rpc.RpcHostConfiguration
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcNotification
import dev.p2pkit.rpc.RpcNotifyResult
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.serialization.builtins.serializer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlin.time.Duration
import kotlin.time.Duration.Companion.milliseconds

@OptIn(ExperimentalCoroutinesApi::class)
class RpcApplicationSessionAuthorizationTest {
    private val procedure = RpcProcedure("private.echo", 1,
        String.serializer(), String.serializer(), String.serializer())
    private val notification = RpcNotification("private.changed", 1, String.serializer())

    private class Fixture(val host: RpcHostEngine, val link: RpcTestLink, val budget: PayloadBudget) {
        suspend fun close() {
            host.close()
            link.close()
            link.clearSent()
            assertEquals(0, host.diagnostics.value.runningCalls)
            assertEquals(0, host.diagnostics.value.queuedCalls)
            assertEquals(0L, budget.retainedBytes.value)
        }
    }

    private fun TestScope.session(principal: String = "employee-a", lifetime: Duration = Duration.INFINITE) =
        RpcApplicationSession(testFingerprint(), principal, "login-$principal", lifetime,
            RpcClock { testScheduler.currentTime })

    private suspend fun TestScope.fixture(
        authenticate: suspend (String) -> RpcAuthorizationScope?,
        authorize: suspend (RpcAuthorizationContext) -> Boolean = { true },
        limits: RpcLimits = RpcLimits(),
        handler: suspend (RpcCallContext, String) -> RpcReply<String, String> = { _, value -> RpcReply.Success(value) },
    ): Fixture {
        val budget = PayloadBudget(8L * 1_048_576)
        val descriptor = registeredScopedProcedure(procedure, { _, request -> authenticate(request) }, authorize, handler)
        val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor), limits, budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION)
        val link = RpcTestLink()
        host.negotiate(link)
        return Fixture(host, link, budget)
    }

    private fun invoke(budget: PayloadBudget, id: String = TEST_REQUEST, value: String = "credential", time: Int = 10_000) =
        WireMessage(WireKind.Invoke, id, TEST_INCARNATION, procedure.name, 1, time, 1,
            body = testBody("\"$value\"", budget))

    private fun control(budget: PayloadBudget, kind: WireKind, id: String = TEST_REQUEST) =
        WireMessage(kind, id, TEST_INCARNATION, procedure.name, 1, attempt = if (kind == WireKind.Status) 2 else 0,
            body = OwnedBytes.copy(payloadSha256("\"credential\"".encodeToByteArray()), budget))

    @Test
    fun delayedSuccessAndApplicationErrorNeverAdoptCurrentEmployeeEvenWithZeroCache() = runTest {
        for (cache in listOf(0L, 1_048_576L)) for (businessError in listOf(false, true)) {
            val original = session()
            val grant = RpcAuthorizationScope(original, "sale-17")
            val gate = CompletableDeferred<Unit>()
            val checked = mutableListOf<RpcAuthorizationContext>()
            var currentEmployee = original.principal
            var authenticationCalls = 0
            var executions = 0
            val f = fixture({ authenticationCalls++; grant }, { context ->
                checked += context
                context.scope.session.principal == currentEmployee
            }, RpcLimits(resultCacheBytes = cache)) { context, _ ->
                assertSame(grant, context.authorizationScope)
                executions++
                gate.await()
                if (businessError) RpcReply.ApplicationError("private-error") else RpcReply.Success("private-result")
            }
            try {
                f.host.deliver(f.link, invoke(f.budget)); runCurrent()
                currentEmployee = "employee-b"
                gate.complete(Unit); runCurrent()
                assertTrue(f.link.sent.isEmpty(), "Original asynchronous output must retain employee-a")
                for (kind in listOf(WireKind.Status, WireKind.Receipt, WireKind.Cancel)) {
                    f.host.deliver(f.link, control(f.budget, kind))
                }
                f.host.deliver(f.link, invoke(f.budget))
                assertTrue(f.link.sent.isEmpty(), "Controls/duplicates cannot borrow employee-b")
                assertTrue(checked.all { it.scope === grant })
                assertTrue(checked.any { it.operation == RpcAuthorizationOperation.Duplicate })
                currentEmployee = original.principal // No revocation occurred; fresh policy may grant recovery.
                f.host.deliver(f.link, control(f.budget, WireKind.Status))
                assertEquals(if (cache == 0L) WireKind.Failure else if (businessError) WireKind.ApplicationError
                    else WireKind.Success, f.link.sent.single().kind)
                if (cache == 0L) assertEquals(WireFailure.ResultUnavailable.code, f.link.sent.single().code)
                assertEquals(1, authenticationCalls)
                assertEquals(1, executions)
            } finally { f.close() }
        }
    }

    @Test
    fun reconnectUsesOriginalScopeAndRevocationDoesNotCloseSharedDevice() = runTest {
        val original = session()
        var authenticated = RpcAuthorizationScope(original, "sale-17")
        val gate = CompletableDeferred<Unit>()
        var executions = 0
        val scopes = mutableListOf<RpcAuthorizationScope>()
        val f = fixture({ authenticated }, { scopes += it.scope; true }) { _, value ->
            executions++
            gate.await()
            RpcReply.Success(value)
        }
        val replacement = RpcTestLink()
        try {
            f.host.deliver(f.link, invoke(f.budget)); runCurrent()
            f.host.negotiate(replacement)
            assertTrue(f.link.sent.isEmpty())
            f.host.revokeApplicationSession(original)
            assertEquals(dev.p2pkit.core.ConnectionState.Connected, replacement.transportState.value)
            // Reusing the same strings does not resurrect the exact revoked login.
            authenticated = RpcAuthorizationScope(session(), "sale-17")
            gate.complete(Unit); runCurrent()
            f.host.deliver(replacement, control(f.budget, WireKind.Status))
            f.host.deliver(replacement, invoke(f.budget))
            assertTrue(replacement.sent.isEmpty())
            f.host.deliver(replacement, invoke(f.budget, TEST_SECOND)); runCurrent()
            assertEquals(WireKind.Success, replacement.sent.single().kind)
            assertEquals(2, executions)
            assertFalse(original.isActive)
            assertSame(original, scopes.first().session)
        } finally {
            f.host.close(); replacement.close(); replacement.clearSent(); f.close()
        }
    }

    @Test
    fun originalZeroCacheSuccessErrorAndBodylessOutputQueuedBeforeRevocationCannotStartLater() = runTest {
        for (kind in listOf(WireKind.Success, WireKind.ApplicationError, WireKind.Failure)) {
            val original = session()
            val f = fixture({ RpcAuthorizationScope(original, "resource") },
                limits = RpcLimits(resultCacheBytes = 0)) { _, value ->
                when (kind) {
                    WireKind.Success -> RpcReply.Success(value)
                    WireKind.ApplicationError -> RpcReply.ApplicationError(value)
                    else -> throw IllegalStateException("handler fixture")
                }
            }
            try {
                f.link.paused = true
                f.host.deliver(f.link, invoke(f.budget)); runCurrent()
                val ticket = f.link.queued.single()
                assertEquals(kind, ticket.message.kind)
                if (kind != WireKind.Failure) assertTrue(checkNotNull(ticket.message.body).size > 0)
                f.host.revokeApplicationSession(original)
                f.link.deliver(ticket)
                assertFalse(ticket.started)
                assertFalse(ticket.completion.await())
                assertTrue(f.link.sent.isEmpty())
            } finally { f.close() }
        }
    }

    @Test
    fun statusAndDuplicatePermissionDoNotImplyRunningDisclosurePermission() = runTest {
        val original = session()
        val grant = RpcAuthorizationScope(original, "sale-17")
        val gate = CompletableDeferred<Unit>()
        val checked = mutableListOf<RpcAuthorizationContext>()
        val f = fixture({ grant }, {
            checked += it
            it.operation != RpcAuthorizationOperation.Running
        }) { _, value -> gate.await(); RpcReply.Success(value) }
        try {
            f.host.deliver(f.link, invoke(f.budget)); runCurrent()
            f.host.deliver(f.link, control(f.budget, WireKind.Status))
            f.host.deliver(f.link, invoke(f.budget))
            assertTrue(f.link.sent.isEmpty())
            assertEquals(2, checked.count { it.operation == RpcAuthorizationOperation.Running })
            assertTrue(checked.all { it.scope === grant })
            gate.complete(Unit); runCurrent()
            assertEquals(WireKind.Success, f.link.sent.single().kind)
        } finally { gate.complete(Unit); runCurrent(); f.close() }
    }

    @Test
    fun freshWriterPolicyAndExpiryDenyAlreadyQueuedResults() = runTest {
        for (expiry in listOf(false, true)) {
            val original = session(lifetime = 10.milliseconds)
            var allowed = true
            val f = fixture({ RpcAuthorizationScope(original) }, { allowed })
            try {
                f.link.paused = true
                f.host.deliver(f.link, invoke(f.budget)); runCurrent()
                val ticket = f.link.queued.single()
                if (expiry) advanceTimeBy(11) else allowed = false
                f.link.deliver(ticket)
                assertFalse(ticket.started)
                assertFalse(ticket.completion.await())
                assertTrue(f.link.sent.isEmpty())
            } finally { f.close() }
        }
    }

    @Test
    fun committedOutputMayFinishAfterRevocationButNextOutputCannotStart() = runTest {
        val original = session()
        val f = fixture({ RpcAuthorizationScope(original) })
        try {
            f.link.onSend = { original.revoke() } // Delivery is already committed; no I/O holds the session gate.
            f.host.deliver(f.link, invoke(f.budget)); runCurrent()
            assertEquals(WireKind.Success, f.link.sent.single().kind)
            assertFalse(original.isActive)
            f.host.deliver(f.link, control(f.budget, WireKind.Status))
            assertEquals(1, f.link.sent.size)
        } finally { f.close() }
    }

    @Test
    fun deniedCancellationCannotCancelOrExposeAnotherSessionWork() = runTest {
        val original = session()
        var permitted = true
        val gate = CompletableDeferred<Unit>()
        var executions = 0
        val f = fixture({ RpcAuthorizationScope(original) }, { permitted }) { _, value ->
            executions++; gate.await(); RpcReply.Success(value)
        }
        try {
            f.host.deliver(f.link, invoke(f.budget)); runCurrent()
            permitted = false
            f.host.deliver(f.link, control(f.budget, WireKind.Cancel)); runCurrent()
            assertEquals(1, f.host.diagnostics.value.runningCalls)
            assertTrue(f.link.sent.isEmpty())
            permitted = true
            gate.complete(Unit); runCurrent()
            assertEquals(WireKind.Success, f.link.sent.single().kind)
            assertEquals(1, executions)
        } finally { gate.complete(Unit); f.close() }
    }

    @Test
    fun queuedCancellationAndDeadlineCompletionRequireOriginalFailureDisclosurePolicy() = runTest {
        for (cancel in listOf(false, true)) {
            val original = session()
            val scopes = mutableListOf<RpcAuthorizationContext>()
            val gate = CompletableDeferred<Unit>()
            var executions = 0
            val f = fixture({ RpcAuthorizationScope(original) }, {
                scopes += it
                it.operation != RpcAuthorizationOperation.Failure
            }, RpcLimits(runningCalls = 1)) { _, value ->
                executions++; gate.await(); RpcReply.Success(value)
            }
            try {
                f.host.deliver(f.link, invoke(f.budget)); runCurrent()
                f.host.deliver(f.link, invoke(f.budget, TEST_SECOND, time = 1)); runCurrent()
                if (cancel) f.host.deliver(f.link, control(f.budget, WireKind.Cancel, TEST_SECOND))
                else { advanceTimeBy(2); f.host.sweep() }
                runCurrent()
                assertEquals(0, f.host.diagnostics.value.queuedCalls)
                assertTrue(f.link.sent.isEmpty(), "Queued finalization must not bypass the scoped authorizer")
                assertTrue(scopes.any { it.requestId.value == TEST_SECOND &&
                    it.operation == RpcAuthorizationOperation.Failure && it.scope.session === original })
                gate.complete(Unit); runCurrent()
                assertEquals(1, executions)
                assertEquals(WireKind.Success, f.link.sent.single().kind)
            } finally { gate.complete(Unit); f.close() }
        }
    }

    @Test
    fun queuedExecutionRechecksScopeBeforeHandlerStart() = runTest {
        val original = session()
        val gate = CompletableDeferred<Unit>()
        var executeSecond = true
        var executions = 0
        val f = fixture({ RpcAuthorizationScope(original) }, {
            it.requestId.value != TEST_SECOND || it.operation != RpcAuthorizationOperation.Execute || executeSecond
        }, RpcLimits(runningCalls = 1)) { _, value ->
            executions++; gate.await(); RpcReply.Success(value)
        }
        try {
            f.host.deliver(f.link, invoke(f.budget)); runCurrent()
            f.host.deliver(f.link, invoke(f.budget, TEST_SECOND)); runCurrent()
            executeSecond = false
            gate.complete(Unit); runCurrent()
            assertEquals(1, executions)
            assertEquals(WireFailure.AccessRevoked.code, f.link.sent.last().code)
            assertEquals(0, f.host.diagnostics.value.runningCalls)
        } finally { gate.complete(Unit); f.close() }
    }

    @Test
    fun revokedRetainedAndMissingExpiredScopedControlsAllRemainSilentAndConservative() = runTest {
        val original = session()
        val f = fixture({ RpcAuthorizationScope(original) })
        try {
            f.host.deliver(f.link, invoke(f.budget)); runCurrent(); f.link.clearSent()
            original.revoke()
            for (kind in listOf(WireKind.Status, WireKind.Cancel, WireKind.Receipt)) {
                f.host.deliver(f.link, control(f.budget, kind))
                f.host.deliver(f.link, control(f.budget, kind, TEST_SECOND))
            }
            advanceTimeBy(60_001); f.host.sweep()
            for (kind in listOf(WireKind.Status, WireKind.Cancel, WireKind.Receipt)) {
                f.host.deliver(f.link, control(f.budget, kind))
            }
            assertTrue(f.link.sent.isEmpty())
            assertEquals(0L, f.budget.retainedBytes.value)
        } finally { f.close() }
    }

    @Test
    fun suspendedAuthenticationAndInvokeOrExecutePolicyCannotHoldRevocationGate() = runTest {
        for (stage in listOf("authenticate", "invoke", "execute")) {
            val original = session()
            val entered = CompletableDeferred<Unit>()
            val release = CompletableDeferred<Unit>()
            var executions = 0
            val f = fixture({
                if (stage == "authenticate") { entered.complete(Unit); release.await() }
                RpcAuthorizationScope(original)
            }, {
                if ((stage == "invoke" && it.operation == RpcAuthorizationOperation.Invoke) ||
                    (stage == "execute" && it.operation == RpcAuthorizationOperation.Execute)
                ) { entered.complete(Unit); release.await() }
                true
            }) { _, value -> executions++; RpcReply.Success(value) }
            try {
                val invocation = async { f.host.deliver(f.link, invoke(f.budget)) }
                runCurrent()
                assertTrue(entered.isCompleted)
                original.revoke() // Must finish without waiting for the application callback.
                release.complete(Unit); runCurrent(); invocation.await()
                assertEquals(0, executions)
                assertEquals(0, f.host.diagnostics.value.runningCalls)
                assertTrue(f.link.sent.isEmpty())
            } finally { release.complete(Unit); f.close() }
        }
    }

    @Test
    fun concurrentAuthenticationGrantsNeverReplaceFirstAdmittedOriginalScope() = runTest {
        val grantA = RpcAuthorizationScope(session("a"), "sale-a")
        val grantB = RpcAuthorizationScope(session("b"), "sale-b")
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        var authentications = 0
        var executions = 0
        val observations = mutableListOf<RpcAuthorizationContext>()
        val f = fixture({
            if (++authentications == 1) { entered.complete(Unit); release.await(); grantA } else grantB
        }, { observations += it; true }) { context, value ->
            assertSame(grantB, context.authorizationScope)
            executions++; RpcReply.Success(value)
        }
        try {
            val old = async { f.host.deliver(f.link, invoke(f.budget)) }
            runCurrent(); assertTrue(entered.isCompleted)
            f.host.deliver(f.link, invoke(f.budget)); runCurrent()
            release.complete(Unit); runCurrent(); old.await()
            assertEquals(1, executions)
            assertEquals(2, authentications)
            assertTrue(observations.filter { it.operation == RpcAuthorizationOperation.Duplicate ||
                it.operation == RpcAuthorizationOperation.Success }.all { it.scope === grantB })
            assertEquals(2, f.link.sent.size)
        } finally { release.complete(Unit); f.close() }
    }

    @Test
    fun denyDefaultInvalidCredentialsAndWrongPeerNeverExecute() = runTest {
        val configuration = RpcHostConfiguration()
        val original = session()
        var executions = 0
        configuration.registerScoped(procedure, { _, _ -> RpcAuthorizationScope(original) }) { _, value ->
            executions++; RpcReply.Success(value)
        }
        val budget = PayloadBudget(1_048_576)
        val host = RpcHostEngine(backgroundScope, configuration.procedures, RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION)
        val link = RpcTestLink()
        try {
            host.negotiate(link)
            host.deliver(link, invoke(budget)); runCurrent()
            assertTrue(link.sent.isEmpty())
            assertEquals(0L, host.diagnostics.value.acceptedCalls)
        } finally { host.close(); link.close(); link.clearSent() }
        for (grant in listOf(null, RpcAuthorizationScope(RpcApplicationSession(testFingerprint(1), "b", "login-b")))) {
            val f = fixture({ grant }) { _, value -> executions++; RpcReply.Success(value) }
            try {
                f.host.deliver(f.link, invoke(f.budget)); runCurrent()
                assertEquals(0L, f.host.diagnostics.value.acceptedCalls)
                assertEquals(WireFailure.AccessRevoked.code, f.link.sent.single().code)
                assertEquals(dev.p2pkit.rpc.RpcExecutionEvidence.MayHaveExecuted,
                    WireFailure.AccessRevoked.evidence)
            } finally { f.close() }
        }
        assertEquals(0, executions)
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun authenticationTimeoutCancellationAndErrorReleaseDecodedAllowance() = runTest {
        for (timeout in listOf(20, 30_000)) {
            val f = fixture({ awaitCancellation() })
            try {
                val pending = async { f.host.deliver(f.link, invoke(f.budget, time = timeout)) }
                runCurrent(); assertTrue(f.budget.retainedBytes.value >= 32_768)
                advanceTimeBy(minOf(timeout, 5_000).toLong()); runCurrent(); pending.await()
                assertEquals(0L, f.host.diagnostics.value.acceptedCalls)
                assertEquals(0L, f.budget.retainedBytes.value)
            } finally { f.close() }
        }
        val marker = object : Error("authentication fixture") { val owner = Any() }
        val fatal = fixture({ throw marker })
        try {
            assertSame(marker, assertFailsWith<Error> { fatal.host.deliver(fatal.link, invoke(fatal.budget)) })
            assertEquals(0L, fatal.budget.retainedBytes.value)
        } finally { fatal.close() }
        val cancelled = fixture({ throw CancellationException("authentication fixture") })
        try {
            assertFailsWith<CancellationException> { cancelled.host.deliver(cancelled.link, invoke(cancelled.budget)) }
            assertEquals(0L, cancelled.budget.retainedBytes.value)
        } finally { cancelled.close() }
    }

    @Test
    fun authenticationCallbackFailureCannotAssertDefiniteNonexecutionAfterSuspension() = runTest {
        val f = fixture({
            kotlinx.coroutines.yield()
            throw dev.p2pkit.rpc.RpcFailure(dev.p2pkit.rpc.RpcFailureKind.InvalidPayload,
                dev.p2pkit.rpc.RpcFailurePhase.Decoding)
        })
        try {
            val invocation = async { f.host.deliver(f.link, invoke(f.budget)) }
            runCurrent(); invocation.await()
            assertEquals(WireFailure.AccessRevoked.code, f.link.sent.single().code)
            assertEquals(dev.p2pkit.rpc.RpcExecutionEvidence.MayHaveExecuted, WireFailure.AccessRevoked.evidence)
            assertEquals(0L, f.host.diagnostics.value.acceptedCalls)
            assertEquals(0L, f.budget.retainedBytes.value)
        } finally { f.close() }
    }

    @Test
    fun scopedNotificationsRecheckOriginalFactsAndQueuedRevocationOrPolicyDenial() = runTest {
        val original = session()
        val grant = RpcAuthorizationScope(original, "notifications")
        var allowed = true
        var checks = 0
        val f = fixture({ grant })
        suspend fun authorize(context: RpcAuthorizationContext): Boolean {
            assertSame(grant, context.scope)
            assertEquals(RpcAuthorizationOperation.Notification, context.operation)
            assertEquals(notification.name, context.procedureName)
            checks++
            return allowed
        }
        try {
            f.link.paused = true
            assertEquals(RpcNotifyResult.Enqueued, f.host.tryNotifyScoped(grant, notification, "private", ::authorize))
            val first = f.link.queued.last()
            allowed = false
            f.link.deliver(first)
            assertFalse(first.started)
            allowed = true
            assertEquals(RpcNotifyResult.Enqueued, f.host.tryNotifyScoped(grant, notification, "private", ::authorize))
            val second = f.link.queued.last()
            original.revoke()
            f.link.deliver(second)
            assertFalse(second.started)
            assertFalse(second.completion.await())
            assertEquals(RpcNotifyResult.NotAuthorized,
                f.host.tryNotifyScoped(grant, notification, "private", ::authorize))
            assertEquals(3, checks)
            assertTrue(f.link.sent.isEmpty())
        } finally { f.close() }
    }

    @Test
    fun bodylessTombstonesKeepBoundedScopeAccountingUntilExpiryNotJustUntilReceipt() = runTest {
        val original = session()
        val f = fixture({ RpcAuthorizationScope(original, "sale-17") })
        try {
            f.host.deliver(f.link, invoke(f.budget)); runCurrent(); f.link.clearSent()
            f.host.deliver(f.link, control(f.budget, WireKind.Receipt))
            assertEquals(256L + 2L * (original.principal.length + original.sessionId.length + "sale-17".length),
                f.budget.retainedBytes.value)
            f.host.deliver(f.link, invoke(f.budget))
            assertEquals(WireFailure.ResultUnavailable.code, f.link.sent.single().code)
            assertEquals(1L, f.host.diagnostics.value.acceptedCalls)
            advanceTimeBy(60_001); f.host.sweep()
            assertEquals(0L, f.budget.retainedBytes.value)
        } finally { f.close() }
    }

    @Test
    fun scopedDecodedRequestRemainsChargedDuringFreshExecutePolicyAndHandler() = runTest {
        val original = session()
        val grant = RpcAuthorizationScope(original, "sale-17")
        val gate = CompletableDeferred<Unit>()
        var observedBudget = 0L
        var currentBudget: PayloadBudget? = null
        val f = fixture({ grant }, {
            if (it.operation == RpcAuthorizationOperation.Execute) {
                observedBudget = checkNotNull(currentBudget).retainedBytes.value
            }
            true
        }) { _, value -> gate.await(); RpcReply.Success(value) }
        currentBudget = f.budget
        try {
            f.host.deliver(f.link, invoke(f.budget)); runCurrent()
            val requestBytes = "\"credential\"".length
            val authority = 256L + 2L * (original.principal.length + original.sessionId.length + grant.resource.length)
            val expected = requestBytes + 256L + RpcBodyCodec.encodingAllowance(procedure.responseLimitBytes) +
                4L * requestBytes + 32_768 + authority
            assertEquals(expected, observedBudget)
            assertEquals(expected, f.budget.retainedBytes.value)
            gate.complete(Unit); runCurrent()
        } finally { gate.complete(Unit); runCurrent(); f.close() }
    }

    @Test
    fun nonCooperativeScopedHandlerRetainsOwnershipUntilActualExitAfterRevocation() = runTest {
        val original = session()
        val release = CompletableDeferred<Unit>()
        val f = fixture({ RpcAuthorizationScope(original) }) { _, value ->
            withContext(NonCancellable) { release.await() }
            RpcReply.Success(value)
        }
        try {
            f.host.deliver(f.link, invoke(f.budget)); runCurrent()
            f.host.revokeApplicationSession(original); runCurrent()
            assertEquals(1, f.host.diagnostics.value.runningCalls)
            assertTrue(f.budget.retainedBytes.value > 0)
            assertTrue(f.link.sent.isEmpty())
            release.complete(Unit); runCurrent()
            assertEquals(0, f.host.diagnostics.value.runningCalls)
            assertTrue(f.link.sent.isEmpty())
        } finally { release.complete(Unit); runCurrent(); f.close() }
    }

    @Test
    fun scopedHandlerAndResultAuthorizerErrorsKeepOriginalFailureAndReleaseOwnership() = runTest {
        val handlerError = object : Error("handler fixture") { val owner = Any() }
        val policyError = object : Error("policy fixture") { val owner = Any() }
        val original = session()
        val errors = mutableListOf<Throwable>()
        val owner = SupervisorJob()
        val executionScope = CoroutineScope(coroutineContext + owner + CoroutineExceptionHandler { _, failure ->
            errors += failure
        })
        val budget = PayloadBudget(1_048_576)
        val descriptor = registeredScopedProcedure(procedure, { _, _ -> RpcAuthorizationScope(original) }, {
            if (it.operation == RpcAuthorizationOperation.Failure) throw policyError
            true
        }) { _, _ -> throw handlerError }
        val host = RpcHostEngine(executionScope, mapOf(descriptor.key to descriptor), RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION)
        val link = RpcTestLink()
        try {
            host.negotiate(link)
            host.deliver(link, invoke(budget)); runCurrent()
            assertSame(handlerError, errors.single())
            assertSame(policyError, handlerError.suppressedExceptions.single())
            assertEquals(0, host.diagnostics.value.runningCalls)
            assertTrue(link.sent.isEmpty())
        } finally { host.close(); owner.cancelAndJoin(); link.close(); link.clearSent() }
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun authorizationIdentifiersAreBoundedRedactedAndSessionsIrreversiblyRevoked() = runTest {
        assertFailsWith<IllegalArgumentException> { session("") }
        assertFailsWith<IllegalArgumentException> { session("x".repeat(257)) }
        assertFailsWith<IllegalArgumentException> { session("employee\n") }
        assertFailsWith<IllegalArgumentException> { session(lifetime = Duration.ZERO) }
        val original = session("private-employee")
        assertFailsWith<IllegalArgumentException> { RpcAuthorizationScope(original, "\u007f") }
        assertFailsWith<IllegalArgumentException> { RpcAuthorizationScope(original, "x".repeat(257)) }
        assertFalse(original.toString().contains(original.principal))
        assertFalse(RpcAuthorizationScope(original, "private-resource").toString().contains("private-resource"))
        assertTrue(original.isActive)
        original.revoke(); original.revoke()
        assertFalse(original.isActive)
        assertFalse(original.commit { error("A revoked session cannot commit") })
        val expired = session(lifetime = 1.milliseconds)
        advanceTimeBy(1)
        assertFalse(expired.isActive)
        assertFalse(expired.commit { error("An expired session cannot commit") })
    }
}
