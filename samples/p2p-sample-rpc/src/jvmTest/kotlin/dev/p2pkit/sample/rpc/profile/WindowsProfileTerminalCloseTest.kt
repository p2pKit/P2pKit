package dev.p2pkit.sample.rpc.profile

import java.util.Collections
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

/** JVM orchestration controls, not Windows native I/O/cancellation or installed-application qualification. */
class WindowsProfileTerminalCloseTest {
    private class Harness {
        val events = Collections.synchronizedList(mutableListOf<String>())
        var deadline: (() -> Unit)? = null
        var work: (() -> Unit)? = null
        var close: () -> Unit = { events += "close" }
        var conceal: () -> Unit = { events += "hide" }
        var completed: () -> Unit = { events += "retired" }
        val owner = WindowsProfileTerminalClose(
            conceal = { conceal() }, retireAllOwners = { close() }, retired = { completed() },
            arm = { expired ->
                events += "arm"
                deadline = expired
                val cancel: () -> Unit = { events += "cancel" }
                cancel
            }, launch = { work = it; events += "launch" }, terminate = { events += "fail:$it" },
        )
    }

    @Test fun constructionAndOrdinaryProfileStopDoNotArmAnApplicationExitDeadline() {
        val h = Harness()
        val files = WindowsProfileFiles.openForValidation(WindowsProfileModel())
        files.close()
        assertTrue(h.events.isEmpty())
        assertEquals(WindowsProfileTerminalClose.State.Idle, h.owner.snapshot)
    }

    @Test fun terminalAdmissionArmsBeforeConcealmentThenOwnsExactlyOneActualClose() {
        val h = Harness()
        assertTrue(h.owner.requestApplicationExit())
        assertFalse(h.owner.requestApplicationExit())
        assertEquals(listOf("arm", "hide", "launch"), h.events)
        assertNotNull(h.work).invoke()
        assertEquals(listOf("arm", "hide", "launch", "close", "retired", "cancel"), h.events)
        assertEquals(WindowsProfileTerminalClose.State.Retired, h.owner.snapshot)
        assertFalse(h.owner.requestApplicationExit())
        assertNotNull(h.deadline).invoke() // Already delivered callbacks are harmless after real close.
        assertEquals(1, h.events.count { it == "retired" })
        assertFalse(h.events.any { it.startsWith("fail:") })
    }

    @Test fun deadlineBeforeOwnerStartsNeverRunsCleanupOrReportsSuccess() {
        val h = Harness()
        h.owner.requestApplicationExit()
        assertNotNull(h.deadline).invoke()
        assertNotNull(h.work).invoke()
        assertNotNull(h.deadline).invoke()
        assertEquals(listOf("arm", "hide", "launch", "fail:Deadline"), h.events)
        assertEquals(WindowsProfileTerminalClose.State.Failed, h.owner.snapshot)
        assertFalse(h.owner.requestApplicationExit())
    }

    @Test fun expiryDuringRealAdapterCloseRetainsOwnerUntilNativeReturnWithoutRetryOrInterrupt() {
        val model = WindowsProfileModel()
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val closed = CountDownLatch(1)
        val failure = AtomicReference<Throwable?>()
        val native = object : WindowsProfileNativeApi by model {
            override fun close(handle: Long) {
                entered.countDown()
                assertTrue(release.await(5, TimeUnit.SECONDS))
                assertFalse(Thread.currentThread().isInterrupted)
                model.close(handle)
                closed.countDown()
            }
        }
        val files = WindowsProfileFiles.openForValidation(native)
        val h = Harness()
        h.close = { files.close() }
        h.owner.requestApplicationExit()
        val worker = thread {
            try { assertNotNull(h.work).invoke() } catch (caught: Throwable) { failure.set(caught) }
        }
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            assertNotNull(h.deadline).invoke()
            assertEquals(1, files.retainedHandleCount)
            assertEquals(1L, closed.count)
            assertFalse(h.owner.requestApplicationExit())
        } finally {
            release.countDown()
            worker.join(5_000)
        }
        assertFalse(worker.isAlive)
        assertEquals(null, failure.get())
        assertEquals(0, files.retainedHandleCount)
        assertEquals(listOf(1L), model.closeCalls)
        assertEquals(1, h.events.count { it == "fail:Deadline" })
        assertFalse("retired" in h.events)
        assertEquals(WindowsProfileTerminalClose.State.Failed, h.owner.snapshot)
    }

    @Test fun concurrentlyDeliveredWorkerCallbackHasExactlyOnePhysicalCleanupOwner() {
        val h = Harness()
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val calls = AtomicInteger()
        h.close = { calls.incrementAndGet(); entered.countDown(); assertTrue(release.await(5, TimeUnit.SECONDS)) }
        h.owner.requestApplicationExit()
        val failure = AtomicReference<Throwable?>()
        fun delivery() = thread {
            try { assertNotNull(h.work).invoke() } catch (caught: Throwable) { failure.set(caught) }
        }
        val first = delivery()
        assertTrue(entered.await(5, TimeUnit.SECONDS))
        val second = delivery()
        try { second.join(250); assertFalse(second.isAlive, "Duplicate delivery must not enter cleanup") }
        finally { release.countDown(); first.join(5_000); second.join(5_000) }
        assertFalse(first.isAlive)
        assertFalse(second.isAlive)
        assertEquals(null, failure.get())
        assertEquals(1, calls.get())
        assertEquals(1, h.events.count { it == "retired" })
    }

    @Test fun stalledCompletionRemainsDeadlineBoundAndLateReturnCannotEraseExpiry() {
        val h = Harness()
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val failure = AtomicReference<Throwable?>()
        h.completed = { entered.countDown(); assertTrue(release.await(5, TimeUnit.SECONDS)) }
        h.owner.requestApplicationExit()
        val worker = thread {
            try { assertNotNull(h.work).invoke() } catch (caught: Throwable) { failure.set(caught) }
        }
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            assertNotNull(h.deadline).invoke()
            assertEquals(WindowsProfileTerminalClose.State.Failed, h.owner.snapshot)
            assertEquals(1, h.events.count { it == "fail:Deadline" })
        } finally { release.countDown(); worker.join(5_000) }
        assertFalse(worker.isAlive)
        assertEquals(null, failure.get())
        assertEquals(WindowsProfileTerminalClose.State.Failed, h.owner.snapshot)
        assertFalse("cancel" in h.events)
    }

    @Test fun ownershipFailureNeverReportsSuccessfulRetirementOrRetriesClose() {
        val h = Harness()
        var calls = 0
        h.close = { calls++; error("synthetic") }
        h.owner.requestApplicationExit()
        assertNotNull(h.work).invoke()
        assertNotNull(h.work).invoke()
        assertNotNull(h.deadline).invoke()
        assertEquals(1, calls)
        assertEquals(1, h.events.count { it == "fail:Ownership" })
        assertFalse("retired" in h.events)
    }

    @Test fun concealmentFailureDoesNotLaunchWorkAndHasOneTerminalOutcome() {
        val h = Harness()
        h.conceal = { error("synthetic") }
        h.owner.requestApplicationExit()
        assertNotNull(h.deadline).invoke()
        assertEquals(listOf("arm", "fail:Concealment"), h.events)
        assertEquals(null, h.work)
    }

    @Test fun cleanupCompletionCallbackFailureFailsWithoutRetryingOwnedCleanup() {
        val h = Harness()
        h.completed = { error("synthetic") }
        h.owner.requestApplicationExit()
        assertNotNull(h.work).invoke()
        assertEquals(listOf("arm", "hide", "launch", "close", "fail:Completion"), h.events)
        assertFalse(h.owner.requestApplicationExit())
    }

    @Test fun synchronousExpiryDuringArmingCannotLeaveAClosingOwnerOrLaunchWork() {
        val events = Collections.synchronizedList(mutableListOf<String>())
        val owner = WindowsProfileTerminalClose({ events += "hide" }, { events += "close" },
            { events += "retired" }, arm = { expire ->
                expire()
                val cancel: () -> Unit = { events += "cancel" }
                cancel
            }, launch = { events += "launch" }, terminate = { events += "fail:$it" })
        assertTrue(owner.requestApplicationExit())
        assertEquals(listOf("fail:Deadline", "cancel"), events)
        assertEquals(WindowsProfileTerminalClose.State.Failed, owner.snapshot)
    }

    @Test fun timerAndWorkerSchedulingFailuresFailClosedWithoutRunningUnscheduledCleanup() {
        for (failTimer in listOf(true, false)) {
            val events = Collections.synchronizedList(mutableListOf<String>())
            val owner = WindowsProfileTerminalClose({ events += "hide" }, { events += "close" },
                { events += "retired" }, arm = {
                    if (failTimer) error("synthetic timer")
                    val cancel: () -> Unit = {}
                    cancel
                }, launch = { error("synthetic worker") }, terminate = { events += "fail:$it" })
            owner.requestApplicationExit()
            assertEquals(if (failTimer) listOf("fail:Scheduling") else listOf("hide", "fail:Scheduling"), events)
            assertFalse(owner.requestApplicationExit())
        }
    }
}
