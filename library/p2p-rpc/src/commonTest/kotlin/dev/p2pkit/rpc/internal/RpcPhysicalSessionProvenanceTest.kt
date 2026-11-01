package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.security.payloadSha256
import dev.p2pkit.rpc.RpcApplicationSession
import dev.p2pkit.rpc.RpcAuthenticationContext
import dev.p2pkit.rpc.RpcAuthorizationContext
import dev.p2pkit.rpc.RpcAuthorizationOperation
import dev.p2pkit.rpc.RpcAuthorizationScope
import dev.p2pkit.rpc.RpcCallContext
import dev.p2pkit.rpc.RpcHostConfiguration
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcNotification
import dev.p2pkit.rpc.RpcNotifyResult
import dev.p2pkit.rpc.RpcPhysicalSessionClosure
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.builtins.serializer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotSame
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class RpcPhysicalSessionProvenanceTest {
    private val procedure = RpcProcedure("physical.echo", 1,
        String.serializer(), String.serializer(), String.serializer())
    private val notification = RpcNotification("physical.update", 1, String.serializer())

    private class Fixture(val host: RpcHostEngine, val budget: PayloadBudget) {
        val links = mutableListOf<RpcTestLink>()
        suspend fun connect(index: Int = 0) = RpcTestLink(index).also { links += it; host.negotiate(it) }
        suspend fun close() {
            host.close()
            links.forEach { it.close(); it.clearSent() }
            assertEquals(0L, budget.retainedBytes.value)
            assertEquals(0, host.diagnostics.value.runningCalls)
        }
    }

    private fun grant() = RpcAuthorizationScope(RpcApplicationSession(testFingerprint(), "employee", "login"))

    private fun TestScope.fixture(
        grant: RpcAuthorizationScope = grant(),
        authenticate: suspend (RpcAuthenticationContext, String) -> RpcAuthorizationScope? = { _, _ -> grant },
        authorize: suspend (RpcAuthorizationContext) -> Boolean = { true },
        handler: suspend (RpcCallContext, String) -> RpcReply<String, String> = { _, value -> RpcReply.Success(value) },
    ): Fixture {
        val config = RpcHostConfiguration()
        config.registerScopedWithPhysicalSession(procedure, authenticate, authorize, handler)
        val budget = PayloadBudget(8L * 1_048_576)
        return Fixture(RpcHostEngine(backgroundScope, config.procedures, RpcLimits(), budget,
            RpcClock { testScheduler.currentTime }, { true }, TEST_INCARNATION), budget)
    }

    private fun invoke(budget: PayloadBudget) = WireMessage(WireKind.Invoke, TEST_REQUEST, TEST_INCARNATION,
        procedure.name, 1, 10_000, 1, body = testBody("\"credential\"", budget))

    private fun control(budget: PayloadBudget, kind: WireKind) = WireMessage(kind, TEST_REQUEST, TEST_INCARNATION,
        procedure.name, 1, body = OwnedBytes.copy(payloadSha256("\"credential\"".encodeToByteArray()), budget))

    @Test
    fun suspendedAuthenticationAndHandlerRetainOriginalAcrossGenerationOneReplacement() = runTest {
        val authenticated = CompletableDeferred<RpcAuthenticationContext>()
        val resume = CompletableDeferred<Unit>()
        val contexts = mutableListOf<RpcAuthorizationContext>()
        var handlerContext: RpcCallContext? = null
        val originalGrant = grant()
        val f = fixture(originalGrant, authenticate = { context, _ ->
            authenticated.complete(context); resume.await(); originalGrant
        }, authorize = { contexts += it; true }, handler = { context, value ->
            handlerContext = context; RpcReply.Success(value)
        })
        try {
            val original = f.connect()
            val invocation = async { f.host.deliver(original, invoke(f.budget)) }
            val captured = authenticated.await()
            val successor = f.connect()
            val other = f.connect(1)
            assertSame(original.identity, captured.peer)
            assertSame(original.physicalSession, captured.physicalSession)
            assertNotSame(original.physicalSession, successor.physicalSession)
            assertEquals(1L, original.physicalSession.generation)
            assertEquals(1L, successor.physicalSession.generation)
            assertFalse(captured.physicalSession.isConnected)
            resume.complete(Unit); invocation.await(); runCurrent()
            assertSame(captured.physicalSession, handlerContext?.physicalSession)
            assertSame(originalGrant, handlerContext?.authorizationScope)
            assertEquals(WireKind.Success, successor.sent.single().kind)
            for (context in contexts) {
                assertSame(captured.physicalSession, context.originalPhysicalSession)
                assertSame(if (context.operation == RpcAuthorizationOperation.Success) successor.physicalSession
                    else original.physicalSession, context.physicalSession)
            }
            assertEquals(listOf(RpcAuthorizationOperation.Invoke, RpcAuthorizationOperation.Execute,
                RpcAuthorizationOperation.Success, RpcAuthorizationOperation.Success), contexts.map { it.operation })
            captured.physicalSession.close()
            assertEquals(1, original.closeCalls)
            assertTrue(successor.physicalSession.isConnected)
            assertTrue(other.physicalSession.isConnected)
            f.host.detach(original)
            assertSame(successor, f.host.trustedLink(testFingerprint()))
        } finally { f.close() }
    }

    @Test
    fun recoveryControlsAndAllDisclosuresKeepOriginalAndActualConnection() = runTest {
        for (result in listOf("success", "application-error", "failure")) {
            val contexts = mutableListOf<RpcAuthorizationContext>()
            val release = CompletableDeferred<Unit>()
            val f = fixture(authorize = { contexts += it; true }, handler = { _, value ->
                release.await()
                when (result) {
                    "success" -> RpcReply.Success(value)
                    "application-error" -> RpcReply.ApplicationError(value)
                    else -> error("handler failure")
                }
            })
            try {
                val original = f.connect()
                f.host.deliver(original, invoke(f.budget)); runCurrent()
                val successor = f.connect()
                contexts.clear()
                f.host.deliver(successor, invoke(f.budget))
                f.host.deliver(successor, control(f.budget, WireKind.Status))
                release.complete(Unit); runCurrent()
                f.host.deliver(successor, control(f.budget, WireKind.Status))
                f.host.deliver(successor, control(f.budget, WireKind.Cancel))
                f.host.deliver(successor, control(f.budget, WireKind.Receipt))
                val expected = when (result) {
                    "success" -> RpcAuthorizationOperation.Success
                    "application-error" -> RpcAuthorizationOperation.ApplicationError
                    else -> RpcAuthorizationOperation.Failure
                }
                assertTrue(contexts.map { it.operation }.containsAll(listOf(RpcAuthorizationOperation.Duplicate,
                    RpcAuthorizationOperation.Running, RpcAuthorizationOperation.Status, expected,
                    RpcAuthorizationOperation.Cancel, RpcAuthorizationOperation.Receipt)))
                contexts.forEach {
                    assertSame(original.physicalSession, it.originalPhysicalSession)
                    assertSame(successor.physicalSession, it.physicalSession)
                }
                assertEquals(1L, f.host.diagnostics.value.acceptedCalls)
            } finally { f.close() }
        }
    }

    @Test
    fun suspendedWriterPolicyCannotSwitchDestinationAfterAnotherReconnect() = runTest {
        val writerEntered = CompletableDeferred<RpcAuthorizationContext>()
        val resume = CompletableDeferred<Unit>()
        var successes = 0
        val f = fixture(authorize = {
            if (it.operation == RpcAuthorizationOperation.Success && ++successes == 2) {
                writerEntered.complete(it); resume.await()
            }
            true
        })
        try {
            val original = f.connect()
            original.paused = true
            f.host.deliver(original, invoke(f.budget)); runCurrent()
            val writer = async { original.deliver(original.queued.single()) }
            val context = writerEntered.await()
            val successor = f.connect()
            resume.complete(Unit); writer.await()
            assertSame(original.physicalSession, context.originalPhysicalSession)
            assertSame(original.physicalSession, context.physicalSession)
            assertTrue(successor.sent.isEmpty())
            assertTrue(original.sent.isEmpty())
            f.host.deliver(successor, control(f.budget, WireKind.Status))
            assertEquals(WireKind.Success, successor.sent.single().kind)
        } finally { f.close() }
    }

    @Test
    fun notificationOriginIsExplicitAndNeverInferredFromCurrentPeer() = runTest {
        val login = grant()
        val f = fixture(login)
        try {
            val original = f.connect()
            val successor = f.connect()
            val contexts = mutableListOf<RpcAuthorizationContext>()
            assertEquals(RpcNotifyResult.Enqueued, f.host.tryNotifyScopedFrom(
                original.physicalSession, login, notification, "private",
            ) {
                contexts += it; true
            })
            assertEquals(2, contexts.size)
            contexts.forEach {
                assertSame(original.physicalSession, it.originalPhysicalSession)
                assertSame(successor.physicalSession, it.physicalSession)
            }
            contexts.clear()
            assertEquals(RpcNotifyResult.Enqueued, f.host.tryNotifyScoped(login, notification, "private", {
                contexts += it; true
            }))
            contexts.forEach {
                assertNull(it.originalPhysicalSession)
                assertSame(successor.physicalSession, it.physicalSession)
            }
            val other = f.connect(1)
            assertFailsWith<IllegalArgumentException> {
                f.host.tryNotifyScopedFrom(other.physicalSession, login, notification, "private") { true }
            }
            successor.paused = true
            assertEquals(RpcNotifyResult.Enqueued, f.host.tryNotifyScopedFrom(
                original.physicalSession, login, notification, "private",
            ) { true })
            f.host.revokeApplicationSession(login.session)
            val sentBefore = successor.sent.size
            successor.deliver(successor.queued.single())
            assertEquals(sentBefore, successor.sent.size)
            assertEquals(RpcPhysicalSessionClosure.Closed, original.physicalSession.closure.value)
            assertTrue(successor.physicalSession.isConnected)
        } finally { f.close() }
    }

    @Test
    fun strictPolicyCanRejectOriginalClosedSessionWithoutBorrowingSuccessor() = runTest {
        val authenticated = CompletableDeferred<Unit>()
        val resume = CompletableDeferred<Unit>()
        var executions = 0
        val login = grant()
        val f = fixture(login, authenticate = { _, _ -> authenticated.complete(Unit); resume.await(); login },
            authorize = {
                it.originalPhysicalSession === it.physicalSession && it.physicalSession?.isConnected == true
            },
            handler = { _, value -> executions++; RpcReply.Success(value) })
        try {
            val original = f.connect()
            val invocation = async { f.host.deliver(original, invoke(f.budget)) }
            authenticated.await()
            val successor = f.connect()
            resume.complete(Unit); invocation.await(); runCurrent()
            assertEquals(0, executions)
            assertEquals(0L, f.host.diagnostics.value.acceptedCalls)
            assertTrue(successor.sent.isEmpty())
        } finally { f.close() }
    }
}
