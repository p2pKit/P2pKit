package dev.p2pkit.sample.android.rpclab

import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import dev.p2pkit.rpc.RpcFailurePhase
import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest

@OptIn(ExperimentalCoroutinesApi::class)
class RpcLabLiveObserverTest {
    private fun host(rows: List<RpcLabPendingRequest> = emptyList(), completed: Long = 0) =
        RpcLabLiveSnapshot(true, "Running", 0, completed, 0, rows)

    @Test
    fun readsImmediatelyThenAtFiveHundredMillisecondsWithOnlyOneOwnedJob() = runTest {
        var reads = 0
        var changes = 0
        val owner = Any()
        val observer = RpcLabLiveObserver(this, { changes++ }, { error("Unexpected read failure") })
        observer.start(owner) { reads++; host() }
        runCurrent()
        assertEquals(1, reads)
        repeat(100) { observer.start(owner) { error("Must not replace an active owner") } }
        assertEquals(1, coroutineContext[Job]!!.children.count { it.isActive })
        advanceTimeBy(499); runCurrent()
        assertEquals(1, reads)
        advanceTimeBy(1); runCurrent()
        assertEquals(2, reads)
        assertEquals(1, changes)
        observer.stop(); observer.stop(); runCurrent()
        assertEquals(0, coroutineContext[Job]!!.children.count { it.isActive })
        assertEquals(RpcLabLiveView(), observer.view.value)
        advanceTimeBy(2_000); runCurrent()
        assertEquals(2, reads)
    }

    @Test
    fun twentyThousandEqualTicksHaveOnePublicationAndOneSafeLogEntry() = runTest {
        var reads = 0
        var publications = 0
        val log = RpcLabEventLog()
        val observer = RpcLabLiveObserver(this, { publications++; log.observed(it) }, { log.failure(it) })
        observer.start(Any()) {
            reads++
            // A native bridge may allocate new wrappers and lists for unchanged rows on every read.
            host(listOf(RpcLabPendingRequest("synthetic-request", "synthetic-fingerprint")))
        }
        runCurrent()
        repeat(20_000) { advanceTimeBy(500); runCurrent() }
        assertEquals(20_001, reads)
        assertEquals(1, publications)
        assertEquals(1, log.lines.value.size)
        assertFalse(log.lines.value.single().contains("synthetic"))
        observer.stop(); runCurrent()
    }

    @Test
    fun pendingInsertReplaceAndRemovePublishExactRowsWithoutActionsOrPrivateLogContent() = runTest {
        val log = RpcLabEventLog()
        var sample = host()
        var changes = 0
        val observer = RpcLabLiveObserver(this, { changes++; log.observed(it) }, { log.failure(it) })
        observer.start(Any()) { sample }; runCurrent()
        val first = RpcLabPendingRequest("synthetic-first", "synthetic-pin-a")
        val second = RpcLabPendingRequest("synthetic-second", "synthetic-pin-b")
        sample = host(listOf(first)); advanceTimeBy(500); runCurrent()
        assertEquals(listOf(first), observer.view.value.snapshot?.pending)
        val afterInsert = log.lines.value.size
        sample = host(listOf(second)); advanceTimeBy(500); runCurrent()
        assertEquals(listOf(second), observer.view.value.snapshot?.pending)
        assertEquals(afterInsert, log.lines.value.size, "Identity-only changes must not be exported")
        sample = host(); advanceTimeBy(500); runCurrent()
        assertEquals(emptyList(), observer.view.value.snapshot?.pending)
        assertEquals(4, changes)
        assertFalse(log.lines.value.joinToString().contains("synthetic"))
        observer.stop(); runCurrent()
    }

    @Test
    fun backgroundAndRoleReplacementInvalidateOldRowsAndRejectAReentrantStaleRead() = runTest {
        val changes = mutableListOf<RpcLabLiveSnapshot>()
        val observer = RpcLabLiveObserver(this, { changes += it }, { error("No read failures expected") })
        val next = RpcLabLiveSnapshot(false, "Negotiating", 0, 0, 0, null)
        observer.start(Any()) {
            observer.stop()
            observer.start(Any()) { next }
            host(listOf(RpcLabPendingRequest("retired-request", "retired-pin")))
        }
        runCurrent()
        assertEquals(listOf(next), changes)
        assertEquals(next, observer.view.value.snapshot)
        assertEquals(1, coroutineContext[Job]!!.children.count { it.isActive })
        observer.stop(); runCurrent()
        assertNull(observer.view.value.snapshot)
        assertEquals(0, coroutineContext[Job]!!.children.count { it.isActive })
    }

    @Test
    fun readFailureClearsStaleRowsDeduplicatesTypedErrorsAndRecoversWithoutChangingTheRole() = runTest {
        var failing = false
        val failures = mutableListOf<Exception>()
        val observer = RpcLabLiveObserver(this, {}, { failures += it })
        val sample = host(listOf(RpcLabPendingRequest("synthetic-request", "synthetic-pin")))
        observer.start(Any()) {
            if (failing) throw RpcFailure(RpcFailureKind.Closed, RpcFailurePhase.Admission)
            sample
        }
        runCurrent()
        failing = true
        repeat(10) { advanceTimeBy(500); runCurrent() }
        assertNull(observer.view.value.snapshot)
        assertEquals("Closed/Admission/NotSent", observer.view.value.problem)
        assertEquals(1, failures.size)
        failing = false; advanceTimeBy(500); runCurrent()
        assertEquals(sample, observer.view.value.snapshot)
        assertNull(observer.view.value.problem)
        observer.stop(); runCurrent()
    }

    @Test
    fun genericReadFailureIsRedactedAndMutableSourceListsCannotChangePublishedRows() = runTest {
        val rows = mutableListOf(RpcLabPendingRequest("synthetic-request", "synthetic-pin"))
        var failing = false
        val observer = RpcLabLiveObserver(this, {}, {})
        observer.start(Any()) {
            if (failing) error("rpc1|private invitation 192.168.1.4 payload")
            host(rows)
        }
        runCurrent()
        rows.clear()
        assertEquals(1, observer.view.value.snapshot?.pending?.size)
        failing = true; advanceTimeBy(500); runCurrent()
        assertEquals(RpcLabLiveView(problem = "LocalOrProtocolFailure"), observer.view.value)
        observer.stop(); runCurrent()
    }

    @Test
    fun manualRefreshNeitherAddsJobsNorMovesTheOriginalTickDeadline() = runTest {
        var reads = 0
        val observer = RpcLabLiveObserver(this, {}, {})
        observer.start(Any()) { reads++; host() }; runCurrent()
        advanceTimeBy(250); runCurrent()
        repeat(20) { observer.refresh() }
        assertEquals(21, reads)
        assertEquals(1, coroutineContext[Job]!!.children.count { it.isActive })
        advanceTimeBy(250); runCurrent()
        assertEquals(22, reads)
        observer.stop(); runCurrent()
        assertNull(observer.refresh())
        assertEquals(22, reads)
    }

    @Test
    fun parentScopeCancellationClearsTheLiveSnapshotAndStopsTheOnlyObserver() = runTest {
        val ownedScope = CoroutineScope(coroutineContext + SupervisorJob(coroutineContext[Job]))
        val observer = RpcLabLiveObserver(ownedScope, {}, {})
        var reads = 0
        observer.start(Any()) { reads++; host() }; runCurrent()
        ownedScope.cancel(); runCurrent()
        assertEquals(RpcLabLiveView(), observer.view.value)
        advanceTimeBy(2_000); runCurrent()
        assertEquals(1, reads)
        observer.stop()
    }

    @Test
    fun activityKeepsPollingOutOfRootCompositionAndNeverGatesBusyOperationsOrOverwritesStatus() {
        val source = activitySource()
        val start = source.substringAfter("private fun startLiveObservation()")
            .substringBefore("private fun refreshStatus()")
        assertTrue(start.contains("mobileConfig != null || !foreground || closing || runtimeOwner.failure != null"))
        assertTrue(start.contains("runtimeOwner.current(token)?.lab === owned"))
        assertTrue(start.contains("owned.diagnostics"))
        assertTrue(start.contains("owned.pending().map"))
        assertFalse(start.contains("busy"))
        for (action in listOf("pairAndConnect(", ".echo(", ".approve(", ".invitation(")) {
            assertFalse(start.contains(action))
        }
        val controls = source.substringAfter("private fun Controls()")
        assertFalse(controls.contains("liveStatus.view.collectAsState()"))
        assertFalse(controls.contains("eventLog.lines.collectAsState()"))
        assertTrue(controls.contains("LiveStatus()"))
        assertTrue(controls.contains("LivePendingRequests()"))
        assertTrue(controls.contains("if (showDiagnostics) Diagnostics()"))
        val refresh = source.substringAfter("private fun refreshStatus()").substringBefore("private fun pair()")
        val ordinaryRefresh = refresh.substringAfter("val sample = liveStatus.refresh()")
        assertFalse(ordinaryRefresh.contains("status ="))
        assertTrue(refresh.substringBefore("val sample = liveStatus.refresh()").contains("if (mobileConfig != null)"))
        assertTrue(refresh.substringBefore("val sample = liveStatus.refresh()").contains("status = eventLog.snapshot"))
        val observer = source.substringAfter("private val liveStatus =").substringBefore("private var showDiagnostics")
        assertFalse(observer.contains("status ="))
        for (boundary in listOf("override fun onPause()", "override fun onStop()", "override fun onDestroy()")) {
            assertTrue(source.substringAfter(boundary).trimStart().startsWith("{\n        liveStatus.stop()"))
        }
        assertTrue(source.substringAfter("private fun stop(").substringBefore("appSwitch.close()")
            .contains("liveStatus.stop()"))
        assertTrue(source.substringAfter("override fun onResume()").substringBefore("override fun onPause()")
            .contains("startLiveObservation()"))
    }

    @Test
    fun cardsAreDistinctAccessibleRoleSpecificAndApprovalRechecksTheExactCurrentRow() {
        val source = activitySource()
        val cards = source.substringAfter("private fun LiveStatus()")
            .substringBefore("private fun LivePendingRequests()")
        assertTrue(cards.contains("Live cards are unavailable during a capacity session."))
        for (label in listOf("Clients", "Pending", "Completed", "Queued", "Connected host", "Connection")) {
            assertTrue(cards.contains("\"$label\""))
        }
        for (color in listOf("primaryContainer", "secondaryContainer", "tertiaryContainer",
            "surfaceContainerHighest")) {
            assertTrue(cards.contains("colors.$color"))
        }
        assertEquals(2, Regex("Row\\(horizontalArrangement").findAll(cards).count())
        assertTrue(cards.contains("semantics(mergeDescendants = true)"))
        assertTrue(cards.contains("sample.safeState == \"Ready\""))
        val pending = source.substringAfter("private fun LivePendingRequests()")
            .substringBefore("private fun Diagnostics()")
        assertTrue(pending.contains("snapshot?.pending?.contains(request) == true"))
        assertTrue(pending.contains("it.requestId == request.requestId && it.fingerprint == request.fingerprint"))
        assertTrue(pending.contains("checkNotNull(lab).approve(request.requestId)"))
        assertTrue(pending.contains("foreground && !busy && !closing && owned != null"))
    }

    private fun activitySource(): String {
        val root = generateSequence(File(checkNotNull(System.getProperty("user.dir")))) { it.parentFile }
            .first { File(it, "settings.gradle.kts").isFile }
        return File(root, "samples/p2p-sample-android/src/debug/java/" +
            "dev/p2pkit/sample/android/rpclab/RpcLabActivity.kt").readText()
    }
}
