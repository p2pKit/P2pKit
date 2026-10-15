package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.rpc.RpcConnectionState
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import dev.p2pkit.rpc.RpcProcedure
import dev.p2pkit.rpc.RpcRetry
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.builtins.serializer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlin.time.Duration.Companion.seconds

/** Deterministic contract regression; the separate lab supplies actual socket evidence. */
@OptIn(ExperimentalCoroutinesApi::class)
class RpcClosedClientTest {
    @Test
    fun retainedCloseRejectsNewCallsBeforeAllocationAndCannotReattach() = runTest {
        val budget = PayloadBudget(4096)
        val engine = RpcClientEngine(backgroundScope, budget, RpcClock { testScheduler.currentTime })
        val procedure = RpcProcedure("echo", 1, String.serializer(), String.serializer(), String.serializer())
        val link = RpcTestLink()
        try {
            repeat(2) {
                engine.close(permanent = true)
                assertEquals(RpcConnectionState.Closed, engine.state.value)
                val failure = assertFailsWith<RpcFailure> {
                    engine.call(procedure, "must not encode or send", 10.seconds, RpcRetry.RecoverOnly())
                }
                assertEquals(RpcFailureKind.NotConnected, failure.kind)
                assertEquals(RpcFailurePhase.Admission, failure.phase)
                assertEquals(RpcExecutionEvidence.NotSent, failure.executionEvidence)
                assertNull(failure.requestId)
                assertEquals(0L, engine.diagnostics.value.acceptedCalls)
                assertEquals(0L, budget.retainedBytes.value)
            }
            assertEquals(RpcFailureKind.Closed, assertFailsWith<RpcFailure> { engine.attach(link) }.kind)
            assertEquals(RpcConnectionState.Closed, engine.state.value)
            assertTrue(link.sent.isEmpty())
        } finally {
            engine.close(permanent = true)
            link.close()
            link.clearSent()
        }
        assertEquals(0L, budget.retainedBytes.value)
    }
}
