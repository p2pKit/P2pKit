package dev.p2pkit.rpc.internal

import dev.p2pkit.rpc.RpcCallObservation
import dev.p2pkit.rpc.RpcCallStage
import dev.p2pkit.rpc.RpcExecutionEvidence
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

class RpcCallObservationTest {
    @Test
    fun anObservationCanBeClaimedOnlyOnceAndMetadataIsNeverInItsStringRepresentation() {
        val observation = RpcCallObservation()
        assertEquals(RpcCallStage.Created, observation.progress.value.stage)
        observation.claim()
        observation.identify("private-id", "private-pin", "private-host")
        assertEquals(RpcCallStage.Encoding, observation.progress.value.stage)
        assertEquals("private-id", observation.progress.value.requestId)
        for (secret in listOf("private-id", "private-pin", "private-host")) {
            assertFalse(observation.progress.value.toString().contains(secret))
        }
        assertFailsWith<IllegalStateException> { observation.claim() }
    }

    @Test
    fun lateQueueCallbacksCannotOverwriteCancellationOrItsNotSentEvidence() {
        val observation = RpcCallObservation()
        observation.claim()
        observation.identify("first-id", "first-pin", "first-host")
        observation.change(RpcCallStage.Queued, 5, RpcExecutionEvidence.NotSent)
        observation.change(RpcCallStage.Cancelled, 6, RpcExecutionEvidence.NotSent)
        observation.change(RpcCallStage.Sending, 7, RpcExecutionEvidence.MayHaveExecuted)
        observation.identify("another-id", "another-pin", "another-host")
        val final = observation.progress.value
        assertEquals(RpcCallStage.Cancelled, final.stage)
        assertEquals(RpcExecutionEvidence.NotSent, final.executionEvidence)
        assertEquals("first-id", final.requestId)
        assertEquals("first-pin", final.peerFingerprint)
        assertEquals(6L, final.elapsedMillis)
    }

    @Test
    fun recoveryDoesNotChangeCorrelationAndElapsedTimeCannotMoveBackward() {
        val observation = RpcCallObservation()
        observation.claim()
        observation.identify("id", "pin", "host")
        observation.change(RpcCallStage.Sending, 5, RpcExecutionEvidence.MayHaveExecuted)
        observation.change(RpcCallStage.AwaitingResponse, 10, RpcExecutionEvidence.MayHaveExecuted)
        observation.change(RpcCallStage.Recovering, 9, RpcExecutionEvidence.MayHaveExecuted)
        assertEquals(10L, observation.progress.value.elapsedMillis)
        observation.change(RpcCallStage.TimedOut, 100, RpcExecutionEvidence.MayHaveExecuted,
            RpcFailureKind.DeadlineExceeded, RpcFailurePhase.AwaitingResponse)
        assertEquals("id", observation.progress.value.requestId)
        assertEquals(RpcFailureKind.DeadlineExceeded, observation.progress.value.failureKind)
        assertEquals(RpcFailurePhase.AwaitingResponse, observation.progress.value.failurePhase)
    }
}
