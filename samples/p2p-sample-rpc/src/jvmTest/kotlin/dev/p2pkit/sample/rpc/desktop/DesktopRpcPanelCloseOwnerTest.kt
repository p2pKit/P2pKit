package dev.p2pkit.sample.rpc.desktop

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class DesktopRpcPanelCloseOwnerTest {
    @Test fun closeWaitsForPhysicalCompletionAndDuplicateRequestsDoNotQueue() {
        val owner = DesktopRpcPanelCloseOwner()
        var finish: ((DesktopRpcCloseResult) -> Unit)? = null
        val first = mutableListOf<DesktopRpcCloseResult>()
        val duplicate = mutableListOf<DesktopRpcCloseResult>()
        owner.request(false, first::add) { finish = it }
        owner.request(false, duplicate::add) { error("Duplicate physical close") }
        assertEquals(emptyList(), first)
        assertEquals(listOf(DesktopRpcCloseResult.Busy), duplicate)
        checkNotNull(finish)(DesktopRpcCloseResult.Closed)
        checkNotNull(finish)(DesktopRpcCloseResult.Closed)
        assertEquals(listOf(DesktopRpcCloseResult.Closed), first)
        owner.request(false, duplicate::add) { error("Already closed") }
        assertEquals(listOf(DesktopRpcCloseResult.Busy, DesktopRpcCloseResult.Closed), duplicate)
    }

    @Test fun failedCleanupIsRetainedAndNeverRetriedOrReportedClosed() {
        val owner = DesktopRpcPanelCloseOwner()
        val results = mutableListOf<DesktopRpcCloseResult>()
        owner.request(false, results::add) { it(DesktopRpcCloseResult.Failed) }
        owner.request(false, results::add) { error("Must retain failed owner") }
        assertEquals(listOf(DesktopRpcCloseResult.Failed, DesktopRpcCloseResult.Failed), results)
    }

    @Test fun synchronousClosePreparationFailureRetainsOwnershipAndReportsOneFailure() {
        val owner = DesktopRpcPanelCloseOwner()
        val results = mutableListOf<DesktopRpcCloseResult>()
        owner.request(false, results::add) { throw IllegalStateException("Synthetic preparation failure") }
        owner.request(false, results::add) { error("Must not retry partially prepared cleanup") }
        assertEquals(listOf(DesktopRpcCloseResult.Failed, DesktopRpcCloseResult.Failed), results)
    }

    @Test fun profileUnlockBlocksCloseWithoutQueuingAReplacementAction() {
        val owner = DesktopRpcPanelCloseOwner()
        var physical: ((DesktopRpcCloseResult) -> Unit)? = null
        val results = mutableListOf<DesktopRpcCloseResult>()
        owner.request(true, results::add) { physical = it }
        assertNull(physical)
        assertEquals(listOf(DesktopRpcCloseResult.Busy), results)
        owner.request(false, results::add) { it(DesktopRpcCloseResult.Closed) }
        assertEquals(listOf(DesktopRpcCloseResult.Busy, DesktopRpcCloseResult.Closed), results)
    }
}
