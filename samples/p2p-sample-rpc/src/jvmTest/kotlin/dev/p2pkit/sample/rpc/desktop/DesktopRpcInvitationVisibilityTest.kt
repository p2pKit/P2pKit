package dev.p2pkit.sample.rpc.desktop

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class DesktopRpcInvitationVisibilityTest {
    @Test
    fun currentInvitationCanPublishOnlyWhileWindowIsActive() {
        val token = Any()
        assertTrue(desktopRpcInvitationVisible(token, token, active = true))
        assertFalse(desktopRpcInvitationVisible(token, token, active = false))
    }

    @Test
    fun completionAfterFocusLossCannotReappearEvenAfterFocusReturns() {
        val requested = Any()
        val afterFocusLoss = Any()
        assertFalse(desktopRpcInvitationVisible(requested, afterFocusLoss, active = false))
        assertFalse(desktopRpcInvitationVisible(requested, afterFocusLoss, active = true))
        assertTrue(desktopRpcInvitationVisible(afterFocusLoss, afterFocusLoss, active = true))
    }

    @Test
    fun stopAndRoleReplacementDoNotReviveAnyPreviousVisibilityGeneration() {
        val first = Any()
        val afterStop = Any()
        val afterReplacement = Any()
        assertFalse(desktopRpcInvitationVisible(first, afterReplacement, active = true))
        assertFalse(desktopRpcInvitationVisible(afterStop, afterReplacement, active = true))
        assertTrue(desktopRpcInvitationVisible(afterReplacement, afterReplacement, active = true))
    }
}
