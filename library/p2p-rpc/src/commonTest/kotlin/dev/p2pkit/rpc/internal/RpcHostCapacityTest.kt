package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcLimits
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcReply
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.builtins.serializer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/** Admission/ordering/accounting models; actual authenticated socket capacity is measured separately. */
@OptIn(ExperimentalCoroutinesApi::class)
class RpcHostCapacityTest {
    // Small explicit schemas isolate call-count limits from the independent shared byte budget.
    private val procedure = RpcProcedure("echo", 1, Int.serializer(), Int.serializer(), Int.serializer(),
        requestLimitBytes = 64, responseLimitBytes = 64, errorLimitBytes = 64)

    private fun id(number: Int): String = number.toString(16).padStart(32, '0')
    private fun invoke(budget: PayloadBudget, number: Int) = WireMessage(
        WireKind.Invoke, id(number), TEST_INCARNATION, "echo", 1, 10_000, 1,
        body = testBody(number.toString(), budget),
    )

    @Test fun bothProfilesFillTheirRunningAndFifoQueueLimitsWithoutLosingAnyPeerOrLease() = runTest {
        for (limits in listOf(RpcLimits.host128(), RpcLimits.host256())) {
            val budget = PayloadBudget(limits.payloadBytes)
            val gate = CompletableDeferred<Unit>()
            val started = mutableListOf<Pair<PeerFingerprint, Int>>()
            val links = List(limits.trustedClients) { RpcTestLink(it) }
            val pins = links.map { checkNotNull(it.identity.fingerprint) }
            assertEquals(limits.trustedClients, pins.toSet().size)
            val descriptor = registeredProcedure(procedure, { true }) { context, value ->
                started += checkNotNull(context.peer.fingerprint) to value
                gate.await()
                RpcReply.Success(value)
            }
            val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor), limits, budget,
                RpcClock { testScheduler.currentTime }, { it in pins }, TEST_INCARNATION)
            try {
                links.forEach { host.negotiate(it); host.deliver(it, invoke(budget, 1)) }
                runCurrent()
                assertEquals(limits.runningCalls, host.diagnostics.value.runningCalls)
                assertEquals(0, host.diagnostics.value.queuedCalls)
                assertEquals(pins.map { it to 1 }, started)
                for (number in 2..3) links.forEach { host.deliver(it, invoke(budget, number)) }
                runCurrent()
                assertEquals(limits.runningCalls, started.size)
                assertEquals(limits.queuedCalls, host.diagnostics.value.queuedCalls)
                host.deliver(links.first(), invoke(budget, 4))
                assertEquals(WireFailure.Overloaded.code, links.first().sent.last().code)
                assertEquals((limits.runningCalls + limits.queuedCalls).toLong(), host.diagnostics.value.acceptedCalls)
                assertEquals(1L, host.diagnostics.value.refusedCalls)
                assertTrue(budget.retainedBytes.value in 1..limits.payloadBytes)

                gate.complete(Unit)
                runCurrent()
                // FIFO promotion cannot let a later peer/wave overtake the queued cohort.
                assertEquals((1..3).flatMap { number -> pins.map { it to number } }, started)
                assertEquals(0, host.diagnostics.value.runningCalls)
                assertEquals(0, host.diagnostics.value.queuedCalls)
                assertEquals(3L * limits.trustedClients, host.diagnostics.value.completedCalls)
                links.forEach { link ->
                    assertEquals((1..3).map(::id), link.sent.filter { it.kind == WireKind.Success }.map { it.id })
                }
            } finally {
                gate.complete(Unit)
                host.close()
                links.forEach { it.clearSent(); it.close() }
            }
            assertEquals(0L, budget.retainedBytes.value)
        }
    }

    @Test fun oneBusyClientStillHasOnlyEightCallsAndRevocationFreesSlotsForTheOther255() = runTest {
        val limits = RpcLimits.host256()
        val budget = PayloadBudget(limits.payloadBytes)
        val gate = CompletableDeferred<Unit>()
        val started = mutableListOf<PeerFingerprint>()
        val links = List(256) { RpcTestLink(it) }
        val pins = links.map { checkNotNull(it.identity.fingerprint) }
        val trusted = pins.toMutableSet()
        assertEquals(256, trusted.size)
        val descriptor = registeredProcedure(procedure, { true }) { context, value ->
            started += checkNotNull(context.peer.fingerprint)
            gate.await()
            RpcReply.Success(value)
        }
        val host = RpcHostEngine(backgroundScope, mapOf(descriptor.key to descriptor), limits, budget,
            RpcClock { testScheduler.currentTime }, { it in trusted }, TEST_INCARNATION)
        try {
            links.forEach { host.negotiate(it) }
            for (number in 1..8) host.deliver(links.first(), invoke(budget, number))
            runCurrent()
            host.deliver(links.first(), invoke(budget, 9))
            assertEquals(WireFailure.Overloaded.code, links.first().sent.last().code)
            links.drop(1).forEach { host.deliver(it, invoke(budget, 1)) }
            runCurrent()
            assertEquals(263L, host.diagnostics.value.acceptedCalls)
            assertEquals(256, host.diagnostics.value.runningCalls)
            assertEquals(7, host.diagnostics.value.queuedCalls)
            assertEquals(8, started.count { it == pins.first() })

            trusted -= pins.first()
            host.revoke(pins.first())
            runCurrent()
            assertEquals(255, host.diagnostics.value.runningCalls)
            assertEquals(0, host.diagnostics.value.queuedCalls)
            assertEquals(1L, host.diagnostics.value.refusedCalls)
            gate.complete(Unit)
            runCurrent()
            assertTrue(links.first().sent.none { it.kind == WireKind.Success })
            links.drop(1).forEach { link -> assertEquals(1, link.sent.count { it.kind == WireKind.Success }) }
            assertEquals(263L, host.diagnostics.value.completedCalls)
            assertEquals(0, host.diagnostics.value.runningCalls)
        } finally {
            gate.complete(Unit)
            host.close()
            links.forEach { it.clearSent(); it.close() }
        }
        assertEquals(0L, budget.retainedBytes.value)
    }
}
