package dev.p2pkit.sample.desktop.ui

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import javax.swing.SwingUtilities
import kotlin.test.Test
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue

class WindowsInstalledUiWorkerTest {
    @Test fun liveWorkerRefusesRetirementWithoutInterruptingOrReplacingItsOwner() {
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val failure = AtomicReference<Throwable?>()
        val worker = Thread {
            try { entered.countDown(); release.await() } catch (caught: Throwable) { failure.set(caught) }
        }
        worker.start()
        try {
            assertTrue(entered.await(2, TimeUnit.SECONDS))
            assertFailsWith<IllegalStateException> { awaitInstalledUiWorker(worker) }
            assertTrue(worker.isAlive)
            assertNull(failure.get())
        } finally { release.countDown(); worker.join(2000) }
        assertFalse(worker.isAlive)
        assertNull(failure.get())
    }

    @Test fun originalWorkerReturnCanBeObservedWithoutAReplacementOrInterrupt() {
        val entered = CountDownLatch(1)
        val worker = Thread { entered.countDown() }
        worker.start()
        assertTrue(entered.await(2, TimeUnit.SECONDS))
        awaitInstalledUiWorker(worker)
        assertFalse(worker.isAlive)
    }

    @Test fun workerCannotObserveItsOwnRetirementAndEdtCannotBlockOnIt() {
        val refusal = AtomicReference<Throwable?>()
        val worker = Thread {
            try { awaitInstalledUiWorker(Thread.currentThread()) } catch (caught: Throwable) { refusal.set(caught) }
        }
        worker.start()
        worker.join(2000)
        assertFalse(worker.isAlive)
        assertIs<IllegalStateException>(refusal.get())
        SwingUtilities.invokeAndWait {
            assertFailsWith<IllegalStateException> { awaitInstalledUiWorker(worker) }
        }
    }
}
