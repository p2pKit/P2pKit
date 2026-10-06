package dev.p2pkit.sample.rpc.desktop

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import java.io.IOException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class DesktopRpcStatusObserverTest {
    @Test
    fun passiveReadsStartWhenReadyRepeatEvery500MillisAndPublishOnlyChanges() = runTest {
        var reads = 0
        var queued = 0
        val seen = mutableListOf<DesktopRpcStatus>()
        val owner = DesktopRpcRunOwner<Any>(backgroundScope,
            readStatus = { _, _ -> reads++; status(queued = queued) }, retire = {})
        backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) {
            owner.snapshots.collect { it.status?.let(seen::add) }
        }
        owner.start("Host", { Any() }) {}
        runCurrent()
        assertEquals(1, reads)
        assertEquals(1, seen.size)
        advanceTimeBy(499)
        runCurrent()
        assertEquals(1, reads)
        advanceTimeBy(1)
        runCurrent()
        assertEquals(2, reads)
        assertEquals(1, seen.size)
        queued = 3
        advanceTimeBy(500)
        runCurrent()
        assertEquals(3, reads)
        assertEquals(listOf(0, 3), seen.map { it.queued })
        owner.stop()
        runCurrent()
        advanceTimeBy(2_000)
        runCurrent()
        assertEquals(3, reads)
        assertNull(owner.snapshot().status)
    }

    @Test
    fun observationDoesNotTakeTheForegroundSlotOrStopDuringAnActiveAction() = runTest {
        var reads = 0
        var actionEntered = false
        val owner = DesktopRpcRunOwner<Any>(backgroundScope,
            readStatus = { _, _ -> reads++; status(clients = reads) }, retire = {})
        owner.start("Host", { Any() }) {}
        runCurrent()
        assertTrue(owner.action { actionEntered = true; awaitCancellation() })
        runCurrent()
        advanceTimeBy(1_000)
        runCurrent()
        assertTrue(actionEntered)
        assertEquals(3, reads)
        assertEquals(3, owner.snapshot().status?.clients)
        assertEquals(DesktopRpcRunOwner.Stage.Working, owner.snapshot().stage)
        assertFalse(owner.action { error("No duplicate user action") })
        owner.stop()
        runCurrent()
    }

    @Test
    fun anInitializingOrStoppedRunIsNeverPassivelyRead() = runTest {
        var reads = 0
        var retired = false
        val owner = DesktopRpcRunOwner<Any>(backgroundScope,
            readStatus = { _, _ -> reads++; status() }, retire = { retired = true })
        owner.start("Host", { Any() }) { awaitCancellation() }
        runCurrent()
        advanceTimeBy(2_000)
        runCurrent()
        assertEquals(0, reads)
        assertNull(owner.snapshot().status)
        owner.stop()
        runCurrent()
        assertTrue(retired)
        assertEquals(0, reads)
    }

    @Test
    fun passiveFailureAndRecoveryNeverOverwriteTheUserActionFailure() = runTest {
        var readFails = false
        val actionFailure = IOException("private action failure")
        val owner = DesktopRpcRunOwner<Any>(backgroundScope,
            readStatus = { _, _ ->
                if (readFails) throw IOException("private passive failure")
                status(completed = 8)
            }, retire = {})
        owner.start("Host", { Any() }) {}
        runCurrent()
        owner.action { throw actionFailure }
        runCurrent()
        assertSame(actionFailure, owner.snapshot().failure)
        readFails = true
        advanceTimeBy(500)
        runCurrent()
        assertSame(actionFailure, owner.snapshot().failure)
        assertNull(owner.snapshot().status)
        assertTrue(owner.snapshot().statusUnavailable)
        assertEquals(DesktopRpcRunOwner.Stage.Ready, owner.snapshot().stage)
        readFails = false
        advanceTimeBy(500)
        runCurrent()
        assertEquals(8L, owner.snapshot().status?.completed)
        assertFalse(owner.snapshot().statusUnavailable)
        assertSame(actionFailure, owner.snapshot().failure)
        owner.stop()
        runCurrent()
    }

    @Test
    fun stopWaitsForThePassiveReaderTerminalBoundaryBeforeRetiringTheRuntime() = runTest {
        val release = CompletableDeferred<Unit>()
        val events = mutableListOf<String>()
        val owner = DesktopRpcRunOwner<Any>(backgroundScope,
            readStatus = { _, _ ->
                events += "reading"
                try { awaitCancellation() }
                finally {
                    withContext(NonCancellable) { release.await() }
                    events += "reader retired"
                }
            }, retire = { events += "runtime retired" })
        owner.start("Host", { Any() }) {}
        runCurrent()
        val stopped = owner.stop()
        runCurrent()
        assertEquals(listOf("reading"), events)
        assertFalse(stopped.isCompleted)
        advanceTimeBy(2_000)
        runCurrent()
        assertEquals(listOf("reading"), events)
        release.complete(Unit)
        runCurrent()
        assertNull(stopped.await())
        assertEquals(listOf("reading", "reader retired", "runtime retired"), events)
    }

    @Test
    fun aLateOldReadCannotPublishOrSurviveIntoTheNextRole() = runTest {
        val release = CompletableDeferred<Unit>()
        val first = Any()
        val second = Any()
        val seen = mutableListOf<String>()
        val owner = DesktopRpcRunOwner<Any>(backgroundScope,
            readStatus = { runtime, _ ->
                if (runtime === first) withContext(NonCancellable) { release.await(); status(fingerprint = "old") }
                else status(fingerprint = "new", role = DesktopRpcRole.Client)
            }, retire = {})
        backgroundScope.launch(UnconfinedTestDispatcher(testScheduler)) {
            owner.snapshots.collect { it.status?.let { current -> seen += current.fingerprint } }
        }
        owner.start("Host", { first }) {}
        runCurrent()
        val stopped = owner.stop()
        runCurrent()
        assertFalse(stopped.isCompleted)
        assertFalse(owner.start("Client", { second }) {})
        assertNull(owner.snapshot().status)
        release.complete(Unit)
        runCurrent()
        assertTrue(stopped.isCompleted)
        assertTrue(owner.start("Client", { second }) {})
        runCurrent()
        assertEquals("new", owner.snapshot().status?.fingerprint)
        assertEquals(listOf("new"), seen)
        owner.stop()
        runCurrent()
    }

    @Test
    fun cancellingTheWindowScopeCannotRetireAnInFlightPassiveReader() = runTest {
        val window = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler))
        val release = CompletableDeferred<Unit>()
        var readRetired = false
        var runtimeRetired = false
        val owner = DesktopRpcRunOwner<Any>(window,
            readStatus = { _, _ ->
                try { awaitCancellation() }
                finally {
                    withContext(NonCancellable) { release.await() }
                    readRetired = true
                }
            }, retire = { assertTrue(readRetired); runtimeRetired = true })
        owner.start("Host", { Any() }) {}
        runCurrent()
        window.cancel()
        runCurrent()
        assertFalse(runtimeRetired)
        release.complete(Unit)
        runCurrent()
        assertTrue(runtimeRetired)
        assertEquals(DesktopRpcRunOwner.Stage.Stopped, owner.snapshot().stage)
    }

    private fun status(
        clients: Int = 0, completed: Long = 0, queued: Int = 0, fingerprint: String = "synthetic host",
        role: DesktopRpcRole = DesktopRpcRole.Host,
    ): DesktopRpcStatus = DesktopRpcStatus(
        role, if (role == DesktopRpcRole.Host) "Running" else "Ready",
        fingerprint, clients, completed, queued, emptyList(),
    )
}
