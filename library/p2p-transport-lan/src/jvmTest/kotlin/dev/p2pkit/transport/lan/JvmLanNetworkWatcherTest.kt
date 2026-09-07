package dev.p2pkit.transport.lan

import java.net.InetAddress
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.async
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/** Deterministic ownership tests for the restartable JVM topology poller. */
@OptIn(ExperimentalCoroutinesApi::class)
class JvmLanNetworkWatcherTest {
    @Test
    fun initialObservationIsReconciledAgainstTheLiveHandleTarget() = runTest {
        val wifiA = target("wifi-a", "192.168.10.2")
        val wifiB = target("wifi-b", "192.168.20.2")
        val current = AtomicReference(wifiB)
        val changes = mutableListOf<Pair<JvmLanBindTarget?, JvmLanBindTarget?>>()
        val watcher = JvmLanNetworkWatcher(
            scope = this,
            pollIntervalMillis = 100,
            snapshotContext = Dispatchers.Unconfined,
            currentTarget = current::get,
            targetChanged = { previous, next, admit ->
                if (admit()) changes += previous to next
            }
        )

        watcher.start(boundTarget = wifiA)
        runCurrent()

        assertEquals(
            listOf<Pair<JvmLanBindTarget?, JvmLanBindTarget?>>(wifiA to wifiB),
            changes
        )
        assertEquals(wifiB, watcher.observedTarget())
        assertTrue(watcher.isActive())
        watcher.stop()
    }

    @Test
    fun stablePollingPublishesEachTopologyChangeOnce() = runTest {
        val wifiA = target("wifi-a", "192.168.10.2")
        val wifiB = target("wifi-b", "192.168.20.2")
        val current = AtomicReference(wifiA)
        val changes = mutableListOf<Pair<JvmLanBindTarget?, JvmLanBindTarget?>>()
        val watcher = JvmLanNetworkWatcher(
            scope = this,
            pollIntervalMillis = 100,
            snapshotContext = Dispatchers.Unconfined,
            currentTarget = current::get,
            targetChanged = { previous, next, admit ->
                if (admit()) changes += previous to next
            }
        )
        watcher.start(boundTarget = wifiA)
        runCurrent()

        advanceTimeBy(100)
        runCurrent()
        assertTrue(changes.isEmpty())

        current.set(wifiB)
        advanceTimeBy(100)
        runCurrent()
        assertEquals(
            listOf<Pair<JvmLanBindTarget?, JvmLanBindTarget?>>(wifiA to wifiB),
            changes
        )

        advanceTimeBy(300)
        runCurrent()
        assertEquals(1, changes.size)
        watcher.stop()
    }

    @Test
    fun retiredIterationCannotOverwriteRestartedWatcherObservation() = runTest {
        val wifiA = target("wifi-a", "192.168.10.2")
        val wifiB = target("wifi-b", "192.168.20.2")
        val stale = target("stale", "192.168.30.2")
        val reads = AtomicInteger()
        lateinit var watcher: JvmLanNetworkWatcher
        val changes = mutableListOf<Pair<JvmLanBindTarget?, JvmLanBindTarget?>>()
        watcher = JvmLanNetworkWatcher(
            scope = this,
            pollIntervalMillis = 100,
            snapshotContext = Dispatchers.Unconfined,
            currentTarget = {
                when (reads.getAndIncrement()) {
                    0 -> wifiA
                    1 -> {
                        // Retire the owner while its poll is outside the gate,
                        // then install a fresh generation before the old value
                        // returns to the publication point.
                        watcher.stop()
                        watcher.start(boundTarget = wifiB)
                        stale
                    }
                    else -> wifiB
                }
            },
            targetChanged = { previous, next, admit ->
                if (admit()) changes += previous to next
            }
        )
        watcher.start(boundTarget = wifiA)
        runCurrent()

        advanceTimeBy(100)
        runCurrent()

        assertEquals(wifiB, watcher.observedTarget())
        assertFalse(changes.any { it.second == stale })
        assertTrue(watcher.isActive())
        watcher.stop()
    }

    @Test
    fun failedInitialSnapshotDoesNotRetainWatcherOwnership() = runTest {
        val wifi = target("wifi", "192.168.10.2")
        val fail = AtomicReference(true)
        val watcher = JvmLanNetworkWatcher(
            scope = this,
            pollIntervalMillis = 100,
            snapshotContext = Dispatchers.Unconfined,
            currentTarget = {
                if (fail.getAndSet(false)) error("injected snapshot failure") else wifi
            },
            targetChanged = { _, _, _ -> error("no topology change expected") }
        )

        watcher.start(boundTarget = wifi)
        runCurrent()
        assertFalse(watcher.isActive())

        watcher.start(boundTarget = wifi)
        runCurrent()
        assertTrue(watcher.isActive())
        watcher.stop()
    }

    @Test
    fun startPublishesTheBoundTargetBeforeTheAsyncSnapshot() = runTest {
        val wifi = target("wifi", "192.168.10.2")
        val reads = AtomicInteger()
        val watcher = JvmLanNetworkWatcher(
            scope = this,
            pollIntervalMillis = 100,
            snapshotContext = Dispatchers.Unconfined,
            currentTarget = {
                reads.incrementAndGet()
                wifi
            },
            targetChanged = { _, _, _ -> error("no topology change expected") }
        )

        watcher.start(boundTarget = wifi)

        assertEquals(0, reads.get(), "start must not enumerate interfaces inline")
        assertEquals(wifi, watcher.observedTarget())
        assertTrue(watcher.isActive())

        runCurrent()
        assertEquals(1, reads.get())
        watcher.stop()
    }

    @Test
    fun snapshotsRunOnTheInjectedIoContext() = runTest {
        val releaseSnapshot = CountDownLatch(1)
        val snapshotExecutor = Executors.newSingleThreadExecutor { runnable ->
            Thread(runnable, "p2pkit-network-probe")
        }
        val snapshotDispatcher = snapshotExecutor.asCoroutineDispatcher()
        val wifi = target("wifi", "192.168.10.2")
        val thread = AtomicReference<String>()
        val entered = CompletableDeferred<Unit>()
        val watcher = JvmLanNetworkWatcher(
            scope = this,
            pollIntervalMillis = 100,
            snapshotContext = snapshotDispatcher,
            currentTarget = {
                thread.set(Thread.currentThread().name)
                entered.complete(Unit)
                wifi
            },
            targetChanged = { _, _, _ -> error("no topology change expected") }
        )
        try {
            // Keep the real probe queued while virtual time advances. This
            // makes a virtual-clock timeout fail deterministically, rather
            // than occasionally beating a correctly dispatched real worker.
            val queueGate = snapshotExecutor.submit { releaseSnapshot.await() }
            watcher.start(boundTarget = wifi)
            runCurrent()
            val snapshotEntered = async(start = CoroutineStart.UNDISPATCHED) {
                withContext(Dispatchers.Default) {
                    withTimeout(1_000) { entered.await() }
                }
            }
            advanceTimeBy(1_001)
            runCurrent()
            assertFalse(snapshotEntered.isCompleted, "virtual time must not expire a real-worker wait")

            releaseSnapshot.countDown()
            snapshotEntered.await()
            queueGate.get(1, TimeUnit.SECONDS)
            assertTrue(thread.get().startsWith("p2pkit-network-probe"))
        } finally {
            watcher.stop()
            releaseSnapshot.countDown()
            snapshotDispatcher.close()
            assertTrue(snapshotExecutor.awaitTermination(1, TimeUnit.SECONDS), "snapshot executor must terminate")
        }
    }

    private fun target(name: String, address: String): JvmLanBindTarget =
        JvmLanBindTarget(
            interfaceName = name,
            address = InetAddress.getByName(address),
            fingerprint = "$name:$address/24"
        )
}
