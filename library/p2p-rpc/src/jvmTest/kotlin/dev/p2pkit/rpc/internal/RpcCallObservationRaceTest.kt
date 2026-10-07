package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.rpc.RpcCallObservation
import dev.p2pkit.rpc.RpcCallStage
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcRetry
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.builtins.serializer
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds

@OptIn(ExperimentalCoroutinesApi::class)
class RpcCallObservationRaceTest {
    @Test
    fun cancellationAfterTicketStartButBeforeCallbackCannotClaimNotSent() = runTest {
        val budget = PayloadBudget(1_048_576)
        val engine = RpcClientEngine(backgroundScope, budget, RpcClock { testScheduler.currentTime })
        val link = RpcTestLink()
        engine.attach(link)
        runCurrent()
        engine.onMessage(link, WireMessage(WireKind.Ready, link.sent.single().id, TEST_INCARNATION, code = 1))
        link.paused = true
        val observation = RpcCallObservation()
        val procedure = RpcProcedure("echo", 1, String.serializer(), String.serializer(), String.serializer())
        val call = async { engine.callWithDetails(procedure, "q", 10.seconds, RpcRetry.RecoverOnly(), observation) }
        runCurrent()
        assertEquals(RpcCallStage.Queued, observation.progress.value.stage)
        val started = CountDownLatch(1)
        val release = CountDownLatch(1)
        val finished = CountDownLatch(1)
        link.beforeStart = { started.countDown(); check(release.await(5, TimeUnit.SECONDS)) }
        val sender = thread(name = "owned-rpc-ticket-race") {
            try { runBlocking { link.deliver(link.queued.single()) } } finally { finished.countDown() }
        }
        try {
            assertTrue(started.await(5, TimeUnit.SECONDS))
            call.cancel(); runCurrent()
            assertTrue(call.isCompleted)
            assertEquals(RpcCallStage.Cancelled, observation.progress.value.stage)
            assertEquals(RpcExecutionEvidence.MayHaveExecuted, observation.progress.value.executionEvidence)
            assertEquals(0, engine.diagnostics.value.queuedCalls)
        } finally {
            release.countDown()
            assertTrue(finished.await(5, TimeUnit.SECONDS))
            sender.join(5_000)
            assertFalse(sender.isAlive)
            engine.close()
            link.close()
            link.clearSent()
        }
        assertEquals(RpcCallStage.Cancelled, observation.progress.value.stage)
        assertEquals(0L, budget.retainedBytes.value)
    }
}
