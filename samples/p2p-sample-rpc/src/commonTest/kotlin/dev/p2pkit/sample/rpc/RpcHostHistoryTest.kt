package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcExecutionEvidence
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class RpcHostHistoryTest {
    private fun row(
        revision: Long, state: RpcRequestOutcome, host: String = "host", id: String = "wire-id",
        refused: Boolean = false, capture: Long = 1,
    ): RpcRequestEntry = RpcRequestEntry(revision, RpcRequestSide.Host, "users.get", 1, id, "pin", "", "", state,
        if (refused) "Unauthorized" else null, 12, if (state == RpcRequestOutcome.Succeeded)
            RpcExecutionEvidence.HandlerFinished else null, host, if (refused) revision else null, capture)

    @Test
    fun queuedMetadataAndDecodedPayloadJoinOnlyTheirExactHostPeerAndWireId() {
        val history = RpcRequestHistory()
        history.observeHost("host", 1, listOf(row(1, RpcRequestOutcome.Queued)))
        val queued = history.entries().single()
        assertEquals(RpcRequestOutcome.Queued, queued.outcome)
        assertTrue(queued.requestPreview.contains("not captured"))
        val local = history.begin(RpcRequestSide.Host, "users.get", 1, "private request", "wire-id", "pin", "host", 1)
        assertEquals(queued.localId, local)
        history.hostResponse(local, "private response")
        history.observeHost("host", 2, listOf(row(2, RpcRequestOutcome.Queued)))
        assertEquals(RpcRequestOutcome.Running, history.entries().single().outcome)
        history.observeHost("host", 3, listOf(row(3, RpcRequestOutcome.Succeeded)))
        val terminal = history.entries().single()
        assertEquals(RpcRequestOutcome.Succeeded, terminal.outcome)
        assertEquals("private request", terminal.requestPreview)
        assertEquals("private response", terminal.responsePreview)
        assertEquals(12L, terminal.elapsedMillis)
        assertEquals(RpcExecutionEvidence.HandlerFinished, terminal.executionEvidence)
        assertFalse(terminal.diagnostics().contains("private"))
        assertTrue(terminal.details().contains("host"))
    }

    @Test
    fun engineFailureAfterHandlerReturnCannotBecomeAFalseSuccessfulRequest() {
        val history = RpcRequestHistory()
        val local = history.begin(RpcRequestSide.Host, "users.get", 1, "request", "wire-id", "pin", "host", 1)
        history.hostResponse(local, "handler response")
        history.observeHost("host", 2, listOf(row(2, RpcRequestOutcome.TimedOut)))
        assertEquals(RpcRequestOutcome.TimedOut, history.entries().single().outcome)
        assertEquals("handler response", history.entries().single().responsePreview)
        history.observeHost("host", 3, listOf(row(3, RpcRequestOutcome.Succeeded)))
        assertEquals(RpcRequestOutcome.TimedOut, history.entries().single().outcome)
        history.observeHost("host", 4, listOf(row(4, RpcRequestOutcome.Queued, capture = 2)))
        assertEquals(2, history.entries().size, "A later post-retention use of a wire ID is a distinct admission")
        history.hostResponse(local, "late response")
        assertEquals("handler response", history.entries().first().responsePreview)
    }

    @Test
    fun refusalAttemptsAndDifferentHostLifetimesCannotReplaceAnEarlierExecution() {
        val history = RpcRequestHistory()
        history.observeHost("host", 1, listOf(row(1, RpcRequestOutcome.Succeeded)))
        history.observeHost("host", 2, listOf(row(2, RpcRequestOutcome.RpcError, refused = true)))
        history.observeHost("another-host", 1, listOf(row(1, RpcRequestOutcome.Queued, host = "another-host")))
        assertEquals(3, history.entries().size)
        assertEquals(RpcRequestOutcome.Succeeded, history.entries().first().outcome)
        assertTrue(history.entries()[1].details().contains("refused invocation attempt"))
        history.retireHost("another-host")
        val last = history.entries().last()
        assertEquals(RpcRequestOutcome.LocalError, last.outcome)
        assertEquals("HostStoppedOutcomeUnobserved", last.errorCode)
        assertEquals(RpcExecutionEvidence.MayHaveExecuted, last.executionEvidence)
    }

    @Test
    fun clearingHistoryDoesNotReimportOldSnapshotRowsAndCaptureRemainsBounded() {
        val history = RpcRequestHistory(1)
        history.observeHost("host", 1, listOf(row(1, RpcRequestOutcome.Succeeded)))
        history.clearCompleted()
        history.observeHost("host", 2, listOf(row(1, RpcRequestOutcome.Succeeded)))
        assertTrue(history.entries().isEmpty())
        val active = history.begin(RpcRequestSide.Client, "users.get", 1, "client request")
        assertNotNull(active)
        history.observeHost("host", 3, listOf(row(3, RpcRequestOutcome.Queued)))
        assertEquals(listOf(active), history.entries().map { it.localId })
        assertEquals(1L, history.droppedCaptures)
        history.observeHost("host", 3, listOf(row(3, RpcRequestOutcome.Queued)))
        assertEquals(1L, history.droppedCaptures)
    }
}
