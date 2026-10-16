package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcCallStage
import dev.p2pkit.rpc.RpcExecutionEvidence
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull

class RpcClientHistoryTest {
    @Test
    fun clientQueueAndEarlyCorrelationBelongOnlyToTheExactLocalRequest() {
        val history = RpcRequestHistory()
        val first = assertNotNull(history.begin(RpcRequestSide.Client, "users.get", 1, "first request"))
        val second = assertNotNull(history.begin(RpcRequestSide.Client, "users.get", 1, "second request"))
        history.observeClient(second, RpcCallStage.Queued, "second-wire-id", "host-pin", "host", 2,
            RpcExecutionEvidence.NotSent)
        val queued = history.entries().last()
        assertEquals(RpcRequestOutcome.Queued, queued.outcome)
        assertEquals("second-wire-id", queued.requestId)
        assertEquals("host-pin", queued.peerFingerprint)
        assertEquals("second request", queued.requestPreview)
        assertEquals("Queued", queued.clientStage)
        assertEquals(null, history.entries().first().requestId)
        assertEquals(first, history.entries().first().localId)
        val revision = history.revision
        history.observeClient(second, RpcCallStage.Queued, "second-wire-id", "host-pin", "host", 2,
            RpcExecutionEvidence.NotSent)
        assertEquals(revision, history.revision, "Unchanged progress cannot invalidate the UI every tick")
        history.observeClient(second, RpcCallStage.Sending, "second-wire-id", "host-pin", "host", 3,
            RpcExecutionEvidence.MayHaveExecuted)
        assertEquals(RpcRequestOutcome.Running, history.entries().last().outcome)
        assertFalse(history.entries().last().diagnostics().contains("second-wire-id"))
        assertFalse(history.entries().last().diagnostics().contains("host-pin"))
    }

    @Test
    fun cancellationBeforeSendKeepsTheExactNotSentEvidenceAndLateProgressCannotReplaceIt() {
        val history = RpcRequestHistory()
        val id = assertNotNull(history.begin(RpcRequestSide.Client, "message.send", 1, "private message"))
        history.observeClient(id, RpcCallStage.Cancelled, "wire-id", "pin", "host", 4,
            RpcExecutionEvidence.NotSent)
        history.finish(id, RpcRequestOutcome.Cancelled, 4, errorCode = "CallerCancelled",
            evidence = RpcExecutionEvidence.NotSent)
        history.observeClient(id, RpcCallStage.Sending, "wire-id", "pin", "host", 5,
            RpcExecutionEvidence.MayHaveExecuted)
        val entry = history.entries().single()
        assertEquals(RpcRequestOutcome.Cancelled, entry.outcome)
        assertEquals(RpcExecutionEvidence.NotSent, entry.executionEvidence)
        assertEquals("wire-id", entry.requestId)
        assertEquals("Cancelled", entry.clientStage)
        history.clearCompleted()
        val next = history.begin(RpcRequestSide.Client, "message.send", 1, "new message")
        history.observeClient(id, RpcCallStage.Succeeded, "wire-id", "pin", "host", 6,
            RpcExecutionEvidence.HandlerFinished)
        assertEquals(next, history.entries().single().localId)
        assertEquals(null, history.entries().single().requestId)
    }
}
