package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.profile.WindowsProfileFiles
import dev.p2pkit.sample.rpc.profile.WindowsProfileModel
import java.io.IOException
import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Actual panel unlock task and actual profile over inert storage; no native-provider or EDT runtime claim. */
@OptIn(ExperimentalCoroutinesApi::class)
class DesktopRpcPanelUnlockTest {
    private class QueuedCompletion : CoroutineDispatcher() {
        val pending = ArrayDeque<Runnable>()
        override fun dispatch(context: CoroutineContext, block: Runnable) { pending.addLast(block) }
        fun deliver() { pending.removeFirst().run() }
    }

    private fun open(model: WindowsProfileModel) = DesktopRpcProfile.openAttempt(
        WindowsProfileFiles.openForValidation(model), "synthetic-panel-unlock-passphrase".toCharArray(),
    )

    @Test fun terminalJoinWaitsForLateProfilePublicationAndNeverStartsTheReadyRole() = runTest {
        val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler))
        val completion = QueuedCompletion()
        val model = WindowsProfileModel()
        var closing = false
        var accepted: DesktopRpcProfileOpenAttempt? = null
        var readyCalls = 0
        var produced: DesktopRpcProfileOpenAttempt? = null
        val unlock = createDesktopRpcProfileUnlock(scope, completion,
            open = { open(model).also { produced = it } }, isClosing = { closing },
            accept = { accepted = it }, ready = { readyCalls++ })
        unlock.start()
        try {
            runCurrent()
            assertEquals(1, completion.pending.size)
            assertNull(accepted)
            assertFalse(unlock.job.isCompleted)
            closing = true
            var retired = false
            val retirement = scope.launch {
                unlock.join()
                checkNotNull(accepted).result.getOrThrow().close()
                retired = true
            }
            runCurrent()
            assertFalse(retired)
            assertFalse(retirement.isCompleted)
            assertTrue(model.remaining > 0)
            completion.deliver()
            runCurrent()
            assertSame(produced, accepted)
            assertTrue(unlock.job.isCompleted)
            assertTrue(retirement.isCompleted)
            assertTrue(retired)
            assertEquals(0, readyCalls)
            assertEquals(0, model.remaining)
            assertTrue(model.store.locks.isEmpty())
            assertEquals(model.closeCalls.distinct(), model.closeCalls)
        } finally {
            while (completion.pending.isNotEmpty()) completion.deliver()
            runCurrent()
            produced?.result?.getOrNull()?.close()
            scope.cancel()
            runCurrent()
        }
    }

    @Test fun cancellationAfterActualOpenCannotDiscardTheUnreturnedProfile() = runTest {
        val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler))
        val model = WindowsProfileModel()
        var produced: DesktopRpcProfileOpenAttempt? = null
        var accepted: DesktopRpcProfileOpenAttempt? = null
        var readyCalls = 0
        val job = createDesktopRpcProfileUnlock(scope, StandardTestDispatcher(testScheduler),
            open = { open(model).also { produced = it; scope.cancel() } }, isClosing = { true },
            accept = { accepted = it }, ready = { readyCalls++ })
        job.start()
        try {
            runCurrent()
            assertTrue(job.job.isCompleted)
            assertTrue(job.job.isCancelled)
            assertSame(produced, accepted)
            assertTrue(checkNotNull(accepted).result.isSuccess)
            assertEquals(0, readyCalls)
        } finally {
            produced?.result?.getOrNull()?.close()
            scope.cancel()
            runCurrent()
        }
        assertEquals(0, model.remaining)
        assertTrue(model.store.locks.isEmpty())
    }

    @Test fun ordinarySuccessfulUnlockPublishesOwnedProfileBeforeReadyAction() = runTest {
        val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler))
        val model = WindowsProfileModel()
        val events = mutableListOf<String>()
        var accepted: DesktopRpcProfileOpenAttempt? = null
        val job = createDesktopRpcProfileUnlock(scope, StandardTestDispatcher(testScheduler),
            open = { open(model) }, isClosing = { false },
            accept = { accepted = it; events += "owned" }, ready = {
                assertTrue(checkNotNull(accepted).result.isSuccess)
                events += "ready"
            })
        job.start()
        try {
            runCurrent()
            assertTrue(job.job.isCompleted)
            assertEquals(listOf("owned", "ready"), events)
        } finally {
            accepted?.result?.getOrNull()?.close()
            scope.cancel()
            runCurrent()
        }
        assertEquals(0, model.remaining)
    }

    @Test fun failedAndEscapingOpenKeepOriginalCleanupUncertaintyWithoutCallingReady() = runTest {
        for (escape in listOf(false, true)) {
            val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler))
            val original = IOException("synthetic unlock result")
            val cleanup = IOException("synthetic explicit cleanup uncertainty")
            var accepted: DesktopRpcProfileOpenAttempt? = null
            var readyCalls = 0
            val job = createDesktopRpcProfileUnlock(scope, StandardTestDispatcher(testScheduler),
                open = {
                    if (escape) throw original
                    DesktopRpcProfileOpenAttempt(Result.failure(original), cleanup)
                }, isClosing = { true }, accept = { accepted = it }, ready = { readyCalls++ })
            job.start()
            try {
                runCurrent()
                assertTrue(job.job.isCompleted)
                assertSame(original, checkNotNull(accepted).result.exceptionOrNull())
                assertSame(if (escape) original else cleanup, checkNotNull(accepted).cleanupFailure)
                assertEquals(0, readyCalls)
            } finally { scope.cancel(); runCurrent() }
        }
    }

    @Test fun rejectedDispatchOrFailedPublicationRetainsTheActualProfileAndJobFailure() = runTest {
        for (rejectDispatch in listOf(true, false)) {
            val original = IOException("synthetic profile delivery failure")
            val reported = mutableListOf<Throwable>()
            val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler) +
                CoroutineExceptionHandler { _, failure -> reported += failure })
            val completion = if (rejectDispatch) object : CoroutineDispatcher() {
                override fun dispatch(context: CoroutineContext, block: Runnable): Unit = throw original
            } else StandardTestDispatcher(testScheduler)
            val model = WindowsProfileModel()
            var readyCalls = 0
            val task = createDesktopRpcProfileUnlock(scope, completion, open = { open(model) },
                isClosing = { true }, accept = { throw original }, ready = { readyCalls++ })
            task.start()
            try {
                runCurrent()
                task.join()
                assertTrue(task.job.isCompleted)
                assertSame(original, task.completionFailure)
                assertEquals(listOf<Throwable>(original), reported)
                assertTrue(checkNotNull(task.attempt).result.isSuccess)
                assertTrue(model.remaining > 0)
                assertEquals(0, readyCalls)
            } finally {
                task.attempt?.result?.getOrNull()?.close()
                scope.cancel()
                runCurrent()
            }
            assertEquals(0, model.remaining)
            assertTrue(model.store.locks.isEmpty())
            assertEquals(model.closeCalls.distinct(), model.closeCalls)
        }
    }

    @Test fun cancelledBeforeDispatchDoesNotOpenAProfileAndStillCompletesPasswordCleanup() = runTest {
        val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler))
        val pass = "synthetic-undispatched-password".toCharArray()
        val model = WindowsProfileModel()
        val task = createDesktopRpcProfileUnlock(scope, StandardTestDispatcher(testScheduler),
            open = { DesktopRpcProfile.openAttempt(WindowsProfileFiles.openForValidation(model), pass) },
            isClosing = { true }, accept = { error("An undispatched open has no profile result") },
            ready = { error("An undispatched open cannot start a role") },
            completionCleanup = { pass.fill('\u0000') })
        task.start()
        scope.cancel()
        runCurrent()
        task.join()
        assertTrue(task.job.isCancelled)
        assertTrue(pass.all { it == '\u0000' })
        assertNull(task.attempt)
        assertEquals(0, model.opens)
        assertEquals(0, model.remaining)
    }

    @Test fun completionAcknowledgmentIncludesPasswordCleanupAndItsFailure() = runTest {
        val scope = CoroutineScope(SupervisorJob() + StandardTestDispatcher(testScheduler))
        val cleanup = IOException("synthetic password cleanup completion")
        val pass = "synthetic-completion-password".toCharArray()
        var cleanupAttempts = 0
        val task = createDesktopRpcProfileUnlock(scope, StandardTestDispatcher(testScheduler),
            open = { error("Cancelled before entry") }, isClosing = { true },
            accept = { error("No attempt to publish") }, ready = { error("No ready action") },
            completionCleanup = { cleanupAttempts++; pass.fill('\u0000'); throw cleanup })
        scope.cancel() // Completion cleanup was installed before first dispatch or even start().
        task.start()
        runCurrent()
        task.join()
        assertTrue(pass.all { it == '\u0000' })
        assertEquals(1, cleanupAttempts)
        assertNull(task.attempt)
        val failure = checkNotNull(task.completionFailure)
        assertTrue(failure.suppressed.any { it === cleanup })
    }
}
