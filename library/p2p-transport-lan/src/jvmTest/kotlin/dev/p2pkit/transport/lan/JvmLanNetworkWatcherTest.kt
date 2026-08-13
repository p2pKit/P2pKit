package dev.p2pkit.transport.lan

import java.net.InetAddress
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
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
            currentTarget = current::get,
            targetChanged = { previous, next, admit ->
                if (admit()) changes += previous to next
            }
        )

        watcher.start(boundTarget = wifiA)

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
            currentTarget = current::get,
            targetChanged = { previous, next, admit ->
                if (admit()) changes += previous to next
            }
        )
        watcher.start(boundTarget = wifiA)

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
            currentTarget = {
                if (fail.getAndSet(false)) error("injected snapshot failure") else wifi
            },
            targetChanged = { _, _, _ -> error("no topology change expected") }
        )

        assertFailsWith<IllegalStateException> { watcher.start(boundTarget = wifi) }
        assertFalse(watcher.isActive())

        watcher.start(boundTarget = wifi)
        assertTrue(watcher.isActive())
        watcher.stop()
    }

    private fun target(name: String, address: String): JvmLanBindTarget =
        JvmLanBindTarget(
            interfaceName = name,
            address = InetAddress.getByName(address),
            fingerprint = "$name:$address/24"
        )
}
