package dev.p2pkit.core.internal

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import java.util.concurrent.ConcurrentLinkedQueue
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlin.test.Test
import kotlin.test.assertTrue

class PeerPublicationConcurrencyTest {
    @Test
    fun interruptedPublicationWaitActuallyPausesAndPreservesInterruption() {
        val started = CountDownLatch(1)
        val stop = AtomicBoolean()
        val interruptionPreserved = AtomicBoolean()
        val failures = ConcurrentLinkedQueue<Throwable>()
        val worker = Thread({
            try {
                Thread.currentThread().interrupt()
                started.countDown()
                val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
                do {
                    pausePeerPublication()
                    check(Thread.currentThread().isInterrupted) { "publication wait consumed the interrupt" }
                } while (!stop.get() && System.nanoTime() < deadline)
                interruptionPreserved.set(Thread.currentThread().isInterrupted)
            } catch (failure: Throwable) {
                failures += failure
            }
        }, "peer-publication-interrupted-wait").apply { isDaemon = true }
        var observedPause = false
        worker.start()
        try {
            assertTrue(started.await(5, TimeUnit.SECONDS), "owned waiter did not start")
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            while (worker.isAlive && System.nanoTime() < deadline) {
                if (worker.state == Thread.State.TIMED_WAITING) {
                    observedPause = true
                    break
                }
                Thread.sleep(1)
            }
        } finally {
            stop.set(true)
            worker.join(5_000)
            assertTrue(!worker.isAlive, "owned publication waiter did not finish")
        }
        assertTrue(failures.isEmpty(), "owned waiter failures: $failures")
        assertTrue(observedPause, "the interrupted waiter must park, not repeatedly return or hot-spin")
        assertTrue(interruptionPreserved.get(), "the caller's interrupt must remain set after the wait")
    }

    @Test
    fun anotherPublisherAndCloseFinishWhileTheOlderCollectorCallbackIsStillRunning() {
        val owner = SupervisorJob()
        val failures = ConcurrentLinkedQueue<Throwable>()
        val scope = CoroutineScope(
            Dispatchers.Unconfined + owner + CoroutineExceptionHandler { _, failure -> failures += failure }
        )
        val registry = PeerRegistry(emptyList(), scope, clock = { 1_000L })
        val callbackEntered = CountDownLatch(1)
        val releaseCallback = CountDownLatch(1)
        val newerFinished = CountDownLatch(1)
        val workers = mutableListOf<Thread>()
        fun startWorker(name: String, block: () -> Unit) {
            val worker = Thread({
                try {
                    block()
                } catch (failure: Throwable) {
                    failures += failure
                }
            }, name).apply { isDaemon = true }
            workers += worker
            worker.start()
        }
        val peer = Peer(PeerId("publication"), "first", Platform.JVM_DESKTOP, setOf(TransportKind.LAN))
        try {
            scope.launch(start = CoroutineStart.UNDISPATCHED) {
                registry.peers.collect { peers ->
                    if (peers.singleOrNull()?.name == "first") {
                        callbackEntered.countDown()
                        releaseCallback.await()
                    }
                }
            }
            startWorker("peer-publication-first") {
                registry.processEvent(PeerEvent.Found(InternalPeer(peer, emptyList())))
            }
            assertTrue(callbackEntered.await(5, TimeUnit.SECONDS), "first callback did not start")
            startWorker("peer-publication-newer") {
                try {
                    registry.processEvent(PeerEvent.Updated(InternalPeer(peer.copy(name = "newer"), emptyList())))
                    registry.close()
                } finally {
                    newerFinished.countDown()
                }
            }
            assertTrue(newerFinished.await(5, TimeUnit.SECONDS), "publication waited for a public callback to return")
            assertTrue(registry.peers.value.isEmpty(), "terminal state must already be visible")
        } finally {
            releaseCallback.countDown()
            workers.forEach { it.join(5_000) }
            owner.cancel()
            assertTrue(workers.none { it.isAlive }, "owned publication workers did not finish")
            assertTrue(owner.isCompleted, "owned state collector did not finish")
        }
        assertTrue(failures.isEmpty(), "owned worker/collector failures: $failures")
        assertTrue(registry.peers.value.isEmpty(), "the older returning publisher must not restore its peers")
    }
}
