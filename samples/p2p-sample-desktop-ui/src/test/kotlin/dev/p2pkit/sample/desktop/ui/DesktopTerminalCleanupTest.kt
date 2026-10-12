package dev.p2pkit.sample.desktop.ui

import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.CompletableFuture
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class DesktopTerminalCleanupTest {
    @Test fun everyStageAndTheRealWorkerDrainMustFinishBeforeSuccess() {
        val events = mutableListOf<String>()
        val cleanup = DesktopTerminalCleanup { action -> events += "dispatch"; action() }
        cleanup.retire(listOf(
            { done -> events += "rpc"; done(true); events += "rpc-return" },
            { done -> events += "ordinary"; done(true) },
            { done -> events += "trace"; done(true) },
        )) { events += "actual-worker-drain" }
        assertEquals(listOf("dispatch", "rpc", "rpc-return", "dispatch", "ordinary", "dispatch", "trace",
            "actual-worker-drain"), events)
    }

    @Test fun failedStageDoesNotSuppressIndependentOwnersAndCannotBecomeSuccess() {
        val events = mutableListOf<String>()
        assertFails {
            DesktopTerminalCleanup { it() }.retire(listOf(
                { done -> events += "rpc-failure"; done(false) },
                { done -> events += "ordinary"; done(true) },
                { done -> events += "trace"; done(true) },
            )) { events += "drain" }
        }
        assertEquals(listOf("rpc-failure", "ordinary", "trace", "drain"), events)
    }

    @Test fun thrownFailureAfterSuccessCallbackIsNotHiddenAndOtherOwnersStillRetire() {
        var independent = 0
        var drains = 0
        assertFails {
            DesktopTerminalCleanup { it() }.retire(listOf(
                { done -> done(true); throw IOException("synthetic after-callback failure") },
                { done -> independent++; done(true) },
            )) { drains++ }
        }
        assertEquals(1, independent)
        assertEquals(1, drains)
    }

    @Test fun duplicateCallbacksCannotRetireAnotherOwnerTwice() {
        var calls = 0
        var drains = 0
        DesktopTerminalCleanup { it() }.retire(listOf(
            { done -> done(true); done(true) },
            { done -> calls++; done(true) },
        )) { drains++ }
        assertEquals(1, calls)
        assertEquals(1, drains)
    }

    @Test fun schedulingFailureDoesNotInventCallbackCompletionOrRunDependentCleanup() {
        val failure = IOException("synthetic dispatch failure")
        var calls = 0
        assertSame(failure, assertFails {
            DesktopTerminalCleanup { throw failure }.retire(listOf({ done -> calls++; done(true) })) { calls++ }
        })
        assertEquals(0, calls)
    }

    @Test fun workerDrainFailureIsNotACompletedApplicationExit() {
        val failure = IOException("synthetic retained worker")
        assertSame(failure, assertFails {
            DesktopTerminalCleanup { it() }.retire(listOf({ done -> done(true) })) { throw failure }
        })
    }

    @Test fun interruptionDoesNotAbandonCleanupOrBecomeSuccessAndIsRestored() {
        assertFalse(Thread.currentThread().isInterrupted)
        var calls = 0
        Thread.currentThread().interrupt()
        try {
            assertFails {
                DesktopTerminalCleanup { it() }.retire(listOf({ done -> calls++; done(true) })) { calls++ }
            }
            assertEquals(2, calls)
            assertTrue(Thread.currentThread().isInterrupted)
        } finally { Thread.interrupted() }
    }

    @Test fun asynchronousCallbackAndLateDuplicatesCannotRetireTheNextOwner() {
        val callbacks = LinkedBlockingQueue<(Boolean) -> Unit>()
        val finished = CompletableFuture<Unit>()
        val drained = AtomicBoolean()
        val releases = List(2) { CompletableFuture<Boolean>() }
        val worker = Thread {
            try {
                DesktopTerminalCleanup { it() }.retire(listOf(
                    { done -> releases[0].thenAccept(done); callbacks.put(done) },
                    { done -> releases[1].thenAccept(done); callbacks.put(done) },
                )) { drained.set(true) }
                finished.complete(Unit)
            } catch (failure: Throwable) { finished.completeExceptionally(failure) }
        }
        try {
            worker.start()
            val first = checkNotNull(callbacks.poll(5, TimeUnit.SECONDS))
            assertFalse(finished.isDone)
            assertFalse(drained.get())
            first(true)
            val second = checkNotNull(callbacks.poll(5, TimeUnit.SECONDS))
            first(true)
            first(false)
            assertFalse(finished.isDone)
            assertFalse(drained.get())
            second(true)
            finished.get(5, TimeUnit.SECONDS)
            assertTrue(drained.get())
        } finally {
            // A late-admitted stage also sees the final release: no unowned worker on assertion failure.
            releases.forEach { it.complete(false) }
            worker.join(5_000)
            assertFalse(worker.isAlive)
        }
    }

    @Test fun interruptionDuringCallbackWaitStillAwaitsRetirementAndRestoresTheFlag() {
        val callbacks = LinkedBlockingQueue<(Boolean) -> Unit>()
        val finished = CompletableFuture<Pair<Throwable?, Boolean>>()
        val release = CompletableFuture<Boolean>()
        val drained = AtomicBoolean()
        val worker = Thread {
            val failure = runCatching {
                DesktopTerminalCleanup { it() }.retire(listOf(
                    { done -> release.thenAccept(done); callbacks.put(done) },
                )) { drained.set(true) }
            }.exceptionOrNull()
            finished.complete(failure to Thread.currentThread().isInterrupted)
        }
        try {
            worker.start()
            val callback = checkNotNull(callbacks.poll(5, TimeUnit.SECONDS))
            // The only wait in this worker is the cleanup result, not a test-controlled delay.
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            while (worker.state != Thread.State.WAITING && !finished.isDone && System.nanoTime() < deadline) {
                Thread.yield()
            }
            assertEquals(Thread.State.WAITING, worker.state)
            worker.interrupt()
            assertFalse(finished.isDone)
            assertFalse(drained.get())
            callback(true)
            val (failure, interrupted) = finished.get(5, TimeUnit.SECONDS)
            assertTrue(failure is IllegalStateException)
            assertTrue(interrupted)
            assertTrue(drained.get())
        } finally {
            release.complete(false)
            worker.join(5_000)
            assertFalse(worker.isAlive)
        }
    }

    @Test fun cancellingTheApplicationScopeIsNotCompletionWhileAChildStillOwnsCleanup() {
        val parent = SupervisorJob()
        val started = CountDownLatch(1)
        val retiring = CountDownLatch(1)
        val release = CompletableDeferred<Unit>()
        val finished = CompletableFuture<Unit>()
        val child = CoroutineScope(parent + Dispatchers.Default).launch {
            try {
                started.countDown()
                awaitCancellation()
            } finally {
                withContext(NonCancellable) {
                    retiring.countDown()
                    release.await()
                }
            }
        }
        val worker = Thread {
            try {
                DesktopTerminalCleanup { it() }.retire(listOf(
                    { done -> parent.cancel(); done(true) },
                )) { runBlocking { parent.join() } }
                finished.complete(Unit)
            } catch (failure: Throwable) { finished.completeExceptionally(failure) }
        }
        try {
            assertTrue(started.await(5, TimeUnit.SECONDS))
            worker.start()
            assertTrue(retiring.await(5, TimeUnit.SECONDS))
            assertTrue(child.isCancelled)
            assertFalse(child.isCompleted)
            assertFalse(parent.isCompleted)
            assertFalse(finished.isDone)
            release.complete(Unit)
            finished.get(5, TimeUnit.SECONDS)
            assertTrue(child.isCompleted)
            assertTrue(parent.isCompleted)
        } finally {
            release.complete(Unit)
            parent.cancel()
            worker.join(5_000)
            assertFalse(worker.isAlive)
            runBlocking { parent.join() }
        }
    }

    @Test fun interruptedWorkerDrainPreservesTheFailureAndRestoresInterruption() {
        val failure = InterruptedException("synthetic drain interruption")
        assertFalse(Thread.currentThread().isInterrupted)
        try {
            assertSame(failure, assertFails {
                DesktopTerminalCleanup { it() }.retire(listOf({ done -> done(true) })) { throw failure }
            })
            assertTrue(Thread.currentThread().isInterrupted)
        } finally { Thread.interrupted() }
    }

    @Test fun successfulIndependentCloseIsAttemptedOnceIncludingLaterDisposal() {
        var calls = 0
        val owner = DesktopOnceCleanup { calls++ }
        owner.close()
        owner.close()
        assertEquals(1, calls)
    }

    @Test fun failedIndependentCloseIsRememberedAndNeverRetriedByDisposal() {
        var calls = 0
        val failure = IOException("synthetic uncertain close")
        val owner = DesktopOnceCleanup { calls++; throw failure }
        assertSame(failure, assertFails { owner.close() })
        assertSame(failure, assertFails { owner.close() })
        assertEquals(1, calls)
    }

    @Test fun windowsExitPolicyDoesNotAccidentallySelectDarwinOrOtherPlatforms() {
        assertTrue(usesWindowsTerminalExit("Windows 11"))
        assertTrue(usesWindowsTerminalExit("windows 10"))
        for (name in listOf("Darwin", "Mac OS X", "Linux", "NotWindows")) {
            assertFalse(usesWindowsTerminalExit(name))
        }
    }
}
