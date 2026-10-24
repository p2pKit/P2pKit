package dev.p2pkit.transport.lan

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import java.io.IOException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame

@OptIn(ExperimentalCoroutinesApi::class)
class SocketPathWatchdogTest {
    @Test fun oneNewSnapshotPer250msCohortStillChecksEveryOriginalOwner() = runTest {
        var safe = true
        var reads = 0
        var predicates = 0
        var rejected = 0
        val monitor = SocketPathWatchdog(backgroundScope) { reads++; safe }
        val owners = List(512) { monitor.register({ predicates++; it }) { rejected++ } }
        runCurrent()
        advanceTimeBy(249); runCurrent()
        assertEquals(0, reads)
        advanceTimeBy(1); runCurrent()
        assertEquals(1, reads)
        assertEquals(512, predicates)
        assertEquals(0, rejected)
        safe = false
        advanceTimeBy(250); runCurrent()
        assertEquals(2, reads)
        assertEquals(1024, predicates)
        assertEquals(512, rejected)
        owners.forEach { it.close() }
        advanceTimeBy(1_000); runCurrent()
        assertEquals(2, reads, "No OS polling remains without socket owners")
    }

    @Test fun closedAndNewOwnersCannotConsumeAnInFlightCohortSnapshot() = runTest {
        lateinit var old: SocketPathWatch
        lateinit var replacement: SocketPathWatch
        lateinit var monitor: SocketPathWatchdog<Boolean>
        var reads = 0
        var oldRejected = 0
        var newRejected = 0
        monitor = SocketPathWatchdog(backgroundScope) {
            reads++
            if (reads == 1) {
                old.close()
                replacement = monitor.register({ it }) { newRejected++ }
            }
            false
        }
        old = monitor.register({ it }) { oldRejected++ }
        runCurrent(); advanceTimeBy(250); runCurrent()
        assertEquals(1, reads)
        assertEquals(0, oldRejected)
        assertEquals(0, newRejected)
        advanceTimeBy(250); runCurrent()
        assertEquals(2, reads)
        assertEquals(0, oldRejected)
        assertEquals(1, newRejected)
        replacement.close()
    }

    @Test fun snapshotFailureClosesEveryOwnerAndIsRetainedInsteadOfSilentlyRestarting() = runTest {
        val original = IOException("synthetic snapshot failure")
        val monitor = SocketPathWatchdog<Boolean>(backgroundScope) { throw original }
        var rejected = 0
        repeat(256) { monitor.register({ true }) { rejected++ } }
        runCurrent(); advanceTimeBy(250); runCurrent()
        assertEquals(256, rejected)
        assertSame(original, assertFailsWith<IOException> { monitor.register({ true }) {} }.cause)
        advanceTimeBy(1_000); runCurrent()
        assertEquals(256, rejected)
    }

    @Test fun predicateFailureRetiresOnlyThatOwnerAndExplicitCloseFencesFutureCallbacks() = runTest {
        var reads = 0
        var rejected = 0
        val monitor = SocketPathWatchdog(backgroundScope) { reads++; true }
        monitor.register({ throw IOException("synthetic per-socket failure") }) { rejected++ }
        val healthy = monitor.register({ it }) { error("Healthy original owner was rejected") }
        runCurrent(); advanceTimeBy(250); runCurrent()
        assertEquals(1, rejected)
        healthy.close()
        advanceTimeBy(1_000); runCurrent()
        assertEquals(1, reads)
        val next = monitor.register({ it }) { error("Replacement consumed retired state") }
        runCurrent(); advanceTimeBy(250); runCurrent()
        assertEquals(2, reads)
        next.close()
    }

    @Test fun externalScopeRetirementClosesOutstandingOwnersAndCannotLeaveAnUnmonitoredSocket() = runTest {
        val parent = SupervisorJob(backgroundScope.coroutineContext[Job])
        val monitor = SocketPathWatchdog(CoroutineScope(backgroundScope.coroutineContext + parent)) { true }
        var rejected = 0
        monitor.register({ it }) { rejected++ }
        runCurrent()
        parent.cancelAndJoin()
        assertEquals(1, rejected)
        assertFalse(parent.isActive)
        assertFailsWith<IOException> { monitor.register({ it }) {} }
    }
}
