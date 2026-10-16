package dev.p2pkit.sample.android.rpclab

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class RpcLabLeaveGateTest {
    @Test fun activeRoleBackConfirmsWithoutStartingCleanupOrLeaving() {
        val gate = RpcLabLeaveGate()
        assertNull(gate.request(foreground = true, needsCleanup = true))
        assertEquals(RpcLabLeaveGate.Phase.Confirm, gate.phase)
        assertNull(gate.request(foreground = true, needsCleanup = true))
        gate.stay()
        assertEquals(RpcLabLeaveGate.Phase.Active, gate.phase)
    }

    @Test fun idleBackStillRequiresCleanupCompletionBeforeExit() {
        val gate = RpcLabLeaveGate()
        val token = assertNotNull(gate.request(foreground = true, needsCleanup = false))
        assertEquals(RpcLabLeaveGate.Phase.Cleaning, gate.phase)
        assertTrue(gate.complete(token, succeeded = true, foreground = true))
        assertEquals(RpcLabLeaveGate.Phase.Left, gate.phase)
    }

    @Test fun duplicateBackAndConfirmationCannotDoublePopOrCancelCleanup() {
        val gate = RpcLabLeaveGate()
        gate.request(foreground = true, needsCleanup = true)
        val token = assertNotNull(gate.confirm(foreground = true))
        assertNull(gate.confirm(foreground = true))
        assertNull(gate.request(foreground = true, needsCleanup = false))
        gate.stay()
        assertEquals(RpcLabLeaveGate.Phase.Cleaning, gate.phase)
        assertTrue(gate.complete(token, succeeded = true, foreground = true))
        assertFalse(gate.complete(token, succeeded = true, foreground = true))
        assertNull(gate.request(foreground = true, needsCleanup = false))
    }

    @Test fun failedCleanupKeepsEntryAndOnlyFreshSuccessfulRetryCanLeave() {
        val gate = RpcLabLeaveGate()
        gate.request(foreground = true, needsCleanup = true)
        val first = assertNotNull(gate.confirm(foreground = true))
        assertFalse(gate.complete(first, succeeded = false, foreground = true))
        assertEquals(RpcLabLeaveGate.Phase.Failed, gate.phase)
        val retry = assertNotNull(gate.confirm(foreground = true))
        assertFalse(gate.complete(first, succeeded = true, foreground = true))
        assertEquals(RpcLabLeaveGate.Phase.Cleaning, gate.phase)
        assertTrue(gate.complete(retry, succeeded = true, foreground = true))
    }

    @Test fun failedCleanupCanStayWithoutPretendingTheOwnerWasRetired() {
        val gate = RpcLabLeaveGate()
        val token = assertNotNull(gate.request(foreground = true, needsCleanup = false))
        assertFalse(gate.complete(token, succeeded = false, foreground = true))
        gate.stay()
        assertEquals(RpcLabLeaveGate.Phase.Active, gate.phase)
        assertNull(gate.request(foreground = true, needsCleanup = true))
        assertEquals(RpcLabLeaveGate.Phase.Confirm, gate.phase)
    }

    @Test fun backgroundCannotRequestOrConfirmAndCompletionDoesNotQueueExit() {
        val gate = RpcLabLeaveGate()
        assertNull(gate.request(foreground = false, needsCleanup = false))
        gate.request(foreground = true, needsCleanup = true)
        assertNull(gate.confirm(foreground = false))
        val token = assertNotNull(gate.confirm(foreground = true))
        assertFalse(gate.complete(token, succeeded = true, foreground = false))
        assertEquals(RpcLabLeaveGate.Phase.Active, gate.phase)
        assertFalse(gate.complete(token, succeeded = true, foreground = true))
        val explicit = assertNotNull(gate.request(foreground = true, needsCleanup = false))
        assertTrue(gate.complete(explicit, succeeded = true, foreground = true))
    }

    @Test fun detachedEntryAndStaleSessionHaveNoAuthorityOverReplacement() {
        val old = RpcLabLeaveGate()
        val token = assertNotNull(old.request(foreground = true, needsCleanup = false))
        old.detach()
        old.detach()
        assertFalse(old.complete(token, succeeded = true, foreground = true))
        assertNull(old.request(foreground = true, needsCleanup = false))
        val replacement = RpcLabLeaveGate()
        val current = assertNotNull(replacement.request(foreground = true, needsCleanup = false))
        assertFalse(replacement.complete(token, succeeded = true, foreground = true))
        assertTrue(replacement.complete(current, succeeded = true, foreground = true))
        assertEquals(RpcLabLeaveGate.Phase.Detached, old.phase)
    }
}
