package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcExecutionEvidence
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class RpcRequestHistoryTest {
    @Test
    fun boundedHistoryEvictsCompletedNotActiveAndNeverRecyclesIds() {
        val history = RpcRequestHistory(2)
        val active = history.begin(RpcRequestSide.Host, "users.get", 1, "{}")
        val completed = history.begin(RpcRequestSide.Client, "users.get", 1, "{}")
        assertNull(history.begin(RpcRequestSide.Client, "users.get", 1, "{}"))
        assertEquals(1L, history.droppedCaptures)
        history.finish(completed, RpcRequestOutcome.Succeeded, 2)
        val next = history.begin(RpcRequestSide.Client, "users.get", 1, "{}")
        assertNotNull(next)
        assertEquals(listOf(active, next), history.entries().map { it.localId })
        assertTrue(next > checkNotNull(completed))
        history.finish(next, RpcRequestOutcome.Succeeded, 1)
        history.clearCompleted()
        assertEquals(listOf(active), history.entries().map { it.localId })
        assertEquals(1L, history.droppedCaptures)
    }

    @Test
    fun firstTerminalObservationWinsAndKeepsExactRpcEvidence() {
        val history = RpcRequestHistory()
        val id = history.begin(RpcRequestSide.Client, "message.send", 1, "request")
        history.finish(id, RpcRequestOutcome.TimedOut, 10_000, requestId = "wire-id",
            errorCode = "DeadlineExceeded.AwaitingResponse", evidence = RpcExecutionEvidence.MayHaveExecuted)
        history.finish(id, RpcRequestOutcome.Succeeded, 10_001, "late response")
        val entry = history.entries().single()
        assertEquals(RpcRequestOutcome.TimedOut, entry.outcome)
        assertEquals("wire-id", entry.requestId)
        assertEquals(RpcExecutionEvidence.MayHaveExecuted, entry.executionEvidence)
        assertEquals("", entry.responsePreview)
    }

    @Test
    fun diagnosticsExcludePayloadIdentityAndCorrelationButDetailsAreExplicit() {
        val history = RpcRequestHistory()
        val id = history.begin(RpcRequestSide.Host, "message.send", 1, "secret request", "private-id", "private-pin")
        history.finish(id, RpcRequestOutcome.Succeeded, 23, "secret response")
        val entry = history.entries().single()
        for (secret in listOf("secret request", "secret response", "private-id", "private-pin")) {
            assertFalse(entry.diagnostics().contains(secret))
            assertFalse(entry.toString().contains(secret))
            assertTrue(entry.details().contains(secret))
        }
    }

    @Test
    fun previewsAreByteBoundedAndNeverSplitUnicode() {
        for (text in listOf("a".repeat(1_000_000), "é".repeat(600), "👋".repeat(400), "مرحبا".repeat(300))) {
            val preview = boundedRpcPreview(text)
            assertTrue(preview.encodeToByteArray().size <= 1_024)
            assertTrue(preview.endsWith("[preview truncated]"))
            assertFalse(preview.contains('\uFFFD'))
        }
        assertEquals("hello 👋", boundedRpcPreview("hello 👋"))
        assertEquals("a".repeat(1_024), boundedRpcPreview("a".repeat(1_024)))
    }

    @Test
    fun clearingHistoryCannotTurnLateCompletionIntoAnotherRequestsResult() {
        val history = RpcRequestHistory(1)
        val old = history.begin(RpcRequestSide.Client, "users.get", 1, "old")
        history.finish(old, RpcRequestOutcome.Succeeded, 1)
        history.clearCompleted()
        val new = history.begin(RpcRequestSide.Client, "users.get", 1, "new")
        history.finish(old, RpcRequestOutcome.RpcError, 3)
        assertEquals(new, history.entries().single().localId)
        assertEquals(RpcRequestOutcome.Running, history.entries().single().outcome)
    }
}
