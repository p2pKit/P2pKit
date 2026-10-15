package dev.p2pkit.sample.android

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SampleRpcAdmissionTest {
    private val idle = SampleRunAdmission(false, false, false, false, false)

    @Test fun rpcEntryRequiresAnActuallyIdleRoomAndSmokeOwner() {
        assertTrue(idle.canEnterRpc)
        for (owned in listOf(
            idle.copy(running = true), idle.copy(starting = true), idle.copy(stopping = true),
            idle.copy(cleanupPending = true), idle.copy(smokeBusy = true),
            idle.copy(roomOwnsKit = true), idle.copy(smokeOwnsKit = true),
            idle.copy(rpcOwnsSection = true), idle.copy(anotherProcessOwner = true),
        )) assertFalse(owned.canEnterRpc, "An existing sample owner must block entry: $owned")
    }

    @Test fun reservedRpcSectionBlocksAllRoomAndSmokeAcquisitionsIncludingStaleFrames() {
        val reserved = idle.copy(rpcOwnsSection = true)
        assertFalse(reserved.canStartOrRetryCleanup)
        assertFalse(reserved.canUseStartAction("Android"))
        assertFalse(reserved.canRunKmpSmoke)
        assertFalse(reserved.canRetryKmpCleanup)
        assertFalse(reserved.canEnterRpc)
    }

    @Test fun retainedRpcRuntimeBlocksNewRoomButKeepsRecoverySectionReachable() {
        val retained = idle.copy(rpcRuntimeOccupied = true)
        assertFalse(retained.canStartOrRetryCleanup)
        assertFalse(retained.canRunKmpSmoke)
        assertTrue(retained.canEnterRpc)
    }

    @Test fun cleanupRetryAdmissionNeverAuthorizesRpcEntry() {
        val room = idle.copy(roomOwnsKit = true, cleanupPending = true)
        assertTrue(room.canStartOrRetryCleanup)
        assertFalse(room.canEnterRpc)
        val smoke = idle.copy(smokeOwnsKit = true)
        assertTrue(smoke.canRetryKmpCleanup)
        assertFalse(smoke.canEnterRpc)
    }
}
