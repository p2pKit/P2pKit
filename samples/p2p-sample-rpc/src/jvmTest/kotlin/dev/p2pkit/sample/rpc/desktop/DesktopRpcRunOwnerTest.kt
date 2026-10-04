package dev.p2pkit.sample.rpc.desktop

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
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
class DesktopRpcRunOwnerTest {
    @Test
    fun oneExplicitRoleRequiresSuccessfulStopBeforeReplacement() = runTest {
        val retired = mutableListOf<Any>()
        val runtime = Any()
        val owner = DesktopRpcRunOwner(backgroundScope) { resource: Any -> retired += resource }
        assertTrue(owner.start("Host", { runtime }) {})
        assertFalse(owner.start("Client", { error("No replacement") }) {})
        assertNull(owner.current())
        runCurrent()
        assertSame(runtime, owner.current())
        assertEquals(DesktopRpcRunOwner.Stage.Ready, owner.snapshot().stage)
        val closed = owner.stop()
        assertSame(closed, owner.stop())
        runCurrent()
        assertNull(closed.await())
        assertEquals(listOf(runtime), retired)
        assertTrue(owner.start("Client", { runtime }) {})
        runCurrent()
        owner.stop()
        runCurrent()
        assertEquals(listOf(runtime, runtime), retired)
    }

    @Test
    fun cancellationBeforeFirstDispatchDoesNotAllocateAndReleasesOwnership() = runTest {
        var allocations = 0
        var retirements = 0
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> retirements++ }
        owner.start("Host", { allocations++; Any() }) {}
        owner.cancelAction()
        runCurrent()
        assertEquals(0, allocations)
        assertEquals(0, retirements)
        assertEquals(DesktopRpcRunOwner.Stage.Stopped, owner.snapshot().stage)
        assertNull(owner.stop().await())
    }

    @Test
    fun stopBeforeFirstDispatchDoesNotAllocate() = runTest {
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> error("No resource to retire") }
        owner.start("Host", { error("Cancelled factory must not run") }) {}
        val result = owner.stop()
        runCurrent()
        assertNull(result.await())
        assertEquals(DesktopRpcRunOwner.Stage.Stopped, owner.snapshot().stage)
    }

    @Test
    fun factoryFailureIsRetainedWithoutInventingAResource() = runTest {
        val failure = IOException("synthetic factory failure")
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> error("No resource to retire") }
        owner.start("Host", { throw failure }) {}
        runCurrent()
        assertSame(failure, owner.snapshot().failure)
        assertEquals(DesktopRpcRunOwner.Stage.Stopped, owner.snapshot().stage)
        assertNull(owner.stop().await())
    }

    @Test
    fun failedInitializationRetiresThePublishedResourceExactlyOnce() = runTest {
        val runtime = Any()
        val failure = IOException("synthetic initialization failure")
        val retired = mutableListOf<Any>()
        val owner = DesktopRpcRunOwner(backgroundScope) { resource: Any -> retired += resource }
        owner.start("Host", { runtime }) { throw failure }
        runCurrent()
        assertEquals(listOf(runtime), retired)
        assertSame(failure, owner.snapshot().failure)
        assertNull(owner.stop().await())
        assertNull(owner.current())
    }

    @Test
    fun lateAllocationAfterStopStillPublishesAndRetiresBeforeReplacement() = runTest {
        val runtime = Any()
        val retired = mutableListOf<Any>()
        val owner = DesktopRpcRunOwner(backgroundScope) { resource: Any -> retired += resource }
        owner.start("Host", { owner.stop(); runtime }) { error("Cancelled initialization must not run") }
        runCurrent()
        assertEquals(listOf(runtime), retired)
        assertEquals(DesktopRpcRunOwner.Stage.Stopped, owner.snapshot().stage)
    }

    @Test
    fun stopWaitsForInitializationFinallyBeforeDestroyingItsStore() = runTest {
        val finish = CompletableDeferred<Unit>()
        val events = mutableListOf<String>()
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> events += "retired" }
        owner.start("Host", { Any() }) {
            try { awaitCancellation() }
            finally { withContext(NonCancellable) { finish.await(); events += "initialization-left" } }
        }
        runCurrent()
        val result = owner.stop()
        runCurrent()
        assertFalse(result.isCompleted)
        assertTrue(events.isEmpty())
        finish.complete(Unit)
        runCurrent()
        assertNull(result.await())
        assertEquals(listOf("initialization-left", "retired"), events)
    }

    @Test
    fun concurrentStopsAwaitOnePhysicalAttemptAndPreventNewActions() = runTest {
        val finish = CompletableDeferred<Unit>()
        var retirements = 0
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> retirements++; finish.await() }
        owner.start("Host", { Any() }) {}
        runCurrent()
        val first = owner.stop()
        val second = owner.stop()
        runCurrent()
        assertSame(first, second)
        assertEquals(1, retirements)
        assertFalse(first.isCompleted)
        assertFalse(owner.start("Client", { Any() }) {})
        assertFalse(owner.action { error("No action after Stop") })
        finish.complete(Unit)
        runCurrent()
        assertNull(first.await())
        assertSame(first, owner.stop())
        assertEquals(1, retirements)
    }

    @Test
    fun failedPhysicalCleanupIsRetainedAndNeverRetried() = runTest {
        val failure: Exception = IOException("synthetic close failure")
        var retirements = 0
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> retirements++; throw failure }
        owner.start("Host", { Any() }) {}
        runCurrent()
        val result = owner.stop()
        runCurrent()
        assertSame(failure, result.await())
        assertSame(failure, owner.snapshot().failure)
        assertSame(result, owner.stop())
        assertSame(failure, owner.stop().await())
        assertEquals(1, retirements)
        assertEquals(DesktopRpcRunOwner.Stage.Failed, owner.snapshot().stage)
        assertFalse(owner.start("Client", { Any() }) {})
        assertNull(owner.current())
    }

    @Test
    fun cancelledQueuedActionNeverEntersAndAllowsNextAction() = runTest {
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> }
        owner.start("Client", { Any() }) {}
        runCurrent()
        var calls = 0
        assertTrue(owner.action { calls++ })
        owner.cancelAction()
        runCurrent()
        assertEquals(0, calls)
        assertEquals(DesktopRpcRunOwner.Stage.Ready, owner.snapshot().stage)
        assertTrue(owner.action { calls++ })
        runCurrent()
        assertEquals(1, calls)
        owner.stop()
        runCurrent()
    }

    @Test
    fun oneActionRejectsDuplicatesAndStopAwaitsItsPhysicalFinally() = runTest {
        val finish = CompletableDeferred<Unit>()
        val events = mutableListOf<String>()
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> events += "retired" }
        owner.start("Client", { Any() }) {}
        runCurrent()
        assertTrue(owner.action {
            try { awaitCancellation() }
            finally { withContext(NonCancellable) { finish.await(); events += "call-left" } }
        })
        runCurrent()
        assertFalse(owner.action { error("No duplicate") })
        val stopped = owner.stop()
        runCurrent()
        assertFalse(stopped.isCompleted)
        assertTrue(events.isEmpty())
        finish.complete(Unit)
        runCurrent()
        assertEquals(listOf("call-left", "retired"), events)
        assertNull(stopped.await())
    }

    @Test
    fun failedActionKeepsItsRuntimeAndDoesNotInventAReply() = runTest {
        val runtime = Any()
        val failure = IOException("synthetic call failure")
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> }
        owner.start("Client", { runtime }) {}
        runCurrent()
        owner.action { throw failure }
        runCurrent()
        assertSame(failure, owner.snapshot().failure)
        assertTrue(owner.owns(runtime))
        assertEquals(DesktopRpcRunOwner.Stage.Ready, owner.snapshot().stage)
        owner.stop()
        runCurrent()
        assertFalse(owner.owns(runtime))
    }

    @Test
    fun cancellingAStopWaiterDoesNotCancelPhysicalCleanup() = runTest {
        val finish = CompletableDeferred<Unit>()
        var retired = false
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> finish.await(); retired = true }
        owner.start("Host", { Any() }) {}
        runCurrent()
        val waiter = backgroundScope.launch { owner.stop().await() }
        runCurrent()
        waiter.cancel()
        runCurrent()
        assertFalse(retired)
        finish.complete(Unit)
        runCurrent()
        assertTrue(retired)
        assertNull(owner.stop().await())
    }

    @Test
    fun cancellingTheApplicationScopeRetiresTheReadyRuntime() = runTest {
        val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler))
        var retirements = 0
        val owner = DesktopRpcRunOwner(scope) { _: Any -> retirements++ }
        owner.start("Client", { Any() }) {}
        runCurrent()
        scope.cancel()
        runCurrent()
        assertEquals(1, retirements)
        assertEquals(DesktopRpcRunOwner.Stage.Stopped, owner.snapshot().stage)
        assertFalse(owner.start("Host", { Any() }) {})
    }

    @Test
    fun applicationCancellationDoesNotCancelSuspendedCleanupOrReplaceItsFailure() = runTest {
        val application = SupervisorJob()
        val scope = CoroutineScope(application + StandardTestDispatcher(testScheduler))
        val release = CompletableDeferred<Unit>()
        val failure: Exception = IOException("synthetic retirement failure")
        var retirements = 0
        val owner = DesktopRpcRunOwner(scope) { _: Any ->
            retirements++
            release.await()
            throw failure
        }
        assertTrue(owner.start("Host", { Any() }) {})
        runCurrent()
        val stopped = owner.stop()
        runCurrent()
        assertEquals(1, retirements)
        assertFalse(stopped.isCompleted)
        scope.cancel()
        runCurrent()
        assertTrue(application.isCompleted)
        assertFalse(stopped.isCancelled)
        assertFalse(stopped.isCompleted)
        assertSame(stopped, owner.stop())
        assertFalse(owner.start("Client", { Any() }) {})
        release.complete(Unit)
        runCurrent()
        assertSame(failure, stopped.await())
        assertSame(failure, owner.snapshot().failure)
        assertEquals(DesktopRpcRunOwner.Stage.Failed, owner.snapshot().stage)
        assertSame(stopped, owner.stop())
        assertEquals(1, retirements)
    }

    @Test
    fun staleRuntimeIsNeverOwnedAfterSuccessfulReplacement() = runTest {
        val first = Any()
        val second = Any()
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> }
        owner.start("Host", { first }) {}
        runCurrent()
        owner.stop()
        runCurrent()
        owner.start("Client", { second }) {}
        runCurrent()
        assertFalse(owner.owns(first))
        assertTrue(owner.owns(second))
        owner.stop()
        runCurrent()
    }

    @Test
    fun cancelledEchoWaitsForActualTerminalCallbackBeforeReleasingItsSlot() = runTest {
        var complete: ((String) -> Unit)? = null
        var cancellations = 0
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> }
        owner.start("Client", { Any() }) {}
        runCurrent()
        owner.action {
            awaitDesktopRpcCompletion<String> { callback ->
                complete = callback
                val cancel: () -> Unit = { cancellations++ }
                cancel
            }
        }
        runCurrent()
        owner.cancelAction()
        runCurrent()
        assertEquals(1, cancellations)
        assertEquals(DesktopRpcRunOwner.Stage.Working, owner.snapshot().stage)
        assertFalse(owner.action { error("Physical callback is not complete") })
        checkNotNull(complete)("cancelled physically")
        runCurrent()
        assertEquals(DesktopRpcRunOwner.Stage.Ready, owner.snapshot().stage)
        owner.stop()
        runCurrent()
    }

    @Test
    fun synchronouslyCompletedEchoDoesNotWaitForAnotherNotification() = runTest {
        var cancellations = 0
        val result = awaitDesktopRpcCompletion<String> { completed ->
            completed("exact reply")
            val cancel: () -> Unit = { cancellations++ }
            cancel
        }
        assertEquals("exact reply", result)
        assertEquals(0, cancellations)
    }

    @Test
    fun stopWaitsForCancelledEchoCallbackBeforeRetiringRuntime() = runTest {
        var complete: ((String) -> Unit)? = null
        var retired = false
        val owner = DesktopRpcRunOwner(backgroundScope) { _: Any -> retired = true }
        owner.start("Client", { Any() }) {}
        runCurrent()
        owner.action {
            awaitDesktopRpcCompletion<String> { callback ->
                complete = callback
                val cancel: () -> Unit = {}
                cancel
            }
        }
        runCurrent()
        val stopped = owner.stop()
        runCurrent()
        assertFalse(retired)
        assertFalse(stopped.isCompleted)
        checkNotNull(complete)("terminal callback")
        runCurrent()
        assertTrue(retired)
        assertNull(stopped.await())
    }

    @Test
    fun errorPresentationDoesNotLeakRawExceptionOrInvitationText() {
        val failure = IOException("rpc1|private test invitation")
        val displayed = desktopRpcFailureText(failure)
        assertFalse(displayed.contains("rpc1"))
        assertFalse(displayed.contains("private test invitation"))
        assertTrue(desktopRpcFailureText(kotlinx.coroutines.CancellationException()).contains("may already"))
    }
}
