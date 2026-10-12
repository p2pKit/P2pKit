package dev.p2pkit.sample.rpc.desktop

import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

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

    @Test fun terminalRequestWaitsForExistingBackAttemptInsteadOfReportingBusyOrRepeatingClose() {
        for (outcome in listOf(DesktopRpcCloseResult.Closed, DesktopRpcCloseResult.Failed)) {
            val owner = DesktopRpcPanelCloseOwner()
            var finish: ((DesktopRpcCloseResult) -> Unit)? = null
            val back = mutableListOf<DesktopRpcCloseResult>()
            val terminal = mutableListOf<DesktopRpcCloseResult>()
            owner.request(false, back::add) { finish = it }
            owner.requestTerminal(terminal::add) { error("Must subscribe, never start another close") }
            assertEquals(emptyList(), terminal)
            checkNotNull(finish)(outcome)
            checkNotNull(finish)(outcome)
            assertEquals(listOf(outcome), back)
            assertEquals(listOf(outcome), terminal)
        }
    }

    @Test fun terminalStartsOneCloseDuringUnlockAndBoundsDuplicateWaiters() {
        val owner = DesktopRpcPanelCloseOwner()
        var finish: ((DesktopRpcCloseResult) -> Unit)? = null
        val back = mutableListOf<DesktopRpcCloseResult>()
        val terminal = mutableListOf<DesktopRpcCloseResult>()
        val duplicate = mutableListOf<DesktopRpcCloseResult>()
        owner.request(true, back::add) { error("Ordinary Back cannot own an active unlock") }
        owner.requestTerminal(terminal::add) { finish = it }
        owner.requestTerminal(duplicate::add) { error("Duplicate terminal attempt") }
        owner.request(false, back::add) { error("Terminal intent seals ordinary admission") }
        assertEquals(listOf(DesktopRpcCloseResult.Busy), duplicate)
        assertEquals(listOf(DesktopRpcCloseResult.Busy, DesktopRpcCloseResult.Busy), back)
        assertEquals(emptyList(), terminal)
        checkNotNull(finish)(DesktopRpcCloseResult.Closed)
        assertEquals(listOf(DesktopRpcCloseResult.Closed), terminal)
    }

    @Test fun terminalCachedFailureAndPreparationFailureNeverRetryPhysicalOwnership() {
        for (preparationFails in listOf(true, false)) {
            val owner = DesktopRpcPanelCloseOwner()
            val results = mutableListOf<DesktopRpcCloseResult>()
            owner.requestTerminal(results::add) {
                if (preparationFails) error("Synthetic scheduling failure")
                else it(DesktopRpcCloseResult.Failed)
            }
            owner.requestTerminal(results::add) { error("Cached failure cannot retry") }
            owner.request(false, results::add) { error("Back cannot retry") }
            assertEquals(List(3) { DesktopRpcCloseResult.Failed }, results)
        }
    }

    @Test fun throwingBackCallbackCannotLoseTheSingleTerminalSubscriber() {
        val owner = DesktopRpcPanelCloseOwner()
        var finish: ((DesktopRpcCloseResult) -> Unit)? = null
        val terminal = mutableListOf<DesktopRpcCloseResult>()
        owner.request(false, { error("Synthetic detached navigation callback") }) { finish = it }
        owner.requestTerminal(terminal::add) { error("Already closing") }
        assertFailsWith<IllegalStateException> { checkNotNull(finish)(DesktopRpcCloseResult.Closed) }
        assertEquals(listOf(DesktopRpcCloseResult.Closed), terminal)
        owner.requestTerminal(terminal::add) { error("Already closed") }
        assertEquals(List(2) { DesktopRpcCloseResult.Closed }, terminal)
    }

    @Test fun drainNotificationRequiresBothActualScopesAndCancellationReturnInEveryOrder() {
        val orders = listOf(listOf(0, 1, 2), listOf(0, 2, 1), listOf(1, 0, 2),
            listOf(1, 2, 0), listOf(2, 0, 1), listOf(2, 1, 0))
        for (order in orders) {
            val expected = CancellationException("synthetic requested scope retirement")
            val outcomes = mutableListOf<Throwable?>()
            val drain = DesktopRpcPanelDrainCompletion(null, expected, outcomes::add)
            val events = listOf({ drain.scopeCompleted(expected) }, { drain.ownersCompleted(null) },
                { drain.cancellationReturned(null) })
            order.forEachIndexed { index, event ->
                events[event]()
                assertEquals(if (index == 2) listOf(null) else emptyList(), outcomes)
            }
            events.forEach { it() }
            assertEquals(listOf(null), outcomes)
        }
    }

    @Test fun cancellationFailureAfterBothScopesCompleteCannotBeReportedAsClean() {
        val expected = CancellationException("synthetic requested scope retirement")
        val failure = IOException("synthetic cancellation completion callback failure")
        val outcomes = mutableListOf<Throwable?>()
        val drain = DesktopRpcPanelDrainCompletion(null, expected, outcomes::add)
        drain.scopeCompleted(expected)
        drain.ownersCompleted(null)
        assertTrue(outcomes.isEmpty())
        drain.cancellationReturned(failure)
        assertSame(failure, outcomes.single())
    }

    @Test fun unexpectedCancellationAndCleanupScopeFailurePreserveTheOriginalPhysicalFailure() {
        val expected = CancellationException("same text is not the same cancellation")
        val unexpected = CancellationException("same text is not the same cancellation")
        val original = IOException("synthetic physical close failure")
        val outcomes = mutableListOf<Throwable?>()
        val drain = DesktopRpcPanelDrainCompletion(original, expected, outcomes::add)
        drain.scopeCompleted(unexpected)
        drain.ownersCompleted(original)
        drain.cancellationReturned(null)
        assertSame(original, outcomes.single())
        assertEquals(listOf(unexpected), original.suppressed.toList())
        val second = mutableListOf<Throwable?>()
        val failedScope = DesktopRpcPanelDrainCompletion(null, expected, second::add)
        failedScope.scopeCompleted(unexpected)
        failedScope.ownersCompleted(null)
        failedScope.cancellationReturned(null)
        assertSame(unexpected, second.single())
    }
}
