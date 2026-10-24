package dev.p2pkit.transport.lan

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withTimeout
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SocketReadinessTest {
    private class Poller : SocketPoller<Int> {
        val started = LinkedBlockingQueue<List<SocketInterest<Int>>>()
        val wakes = Semaphore(0)
        val events = LinkedBlockingQueue<IntArray>()
        val closed = AtomicInteger()
        var closeFailure = false
        var selectFailure = false
        override fun wakeup() { wakes.release() }
        override fun select(interests: List<SocketInterest<Int>>): IntArray {
            started.put(interests)
            check(wakes.tryAcquire(5, TimeUnit.SECONDS)) { "A live owner failed to wake its poller" }
            if (selectFailure) throw IOException("test backend failed")
            return events.poll() ?: IntArray(interests.size)
        }
        override fun close() { closed.incrementAndGet(); if (closeFailure) throw IOException("test retirement") }
    }

    @Test fun lastOwnerJoinsOneSharedWorkerAndReleasesItsBackend() {
        val pollers = mutableListOf<Poller>()
        val readiness = SocketReadiness("readiness-test-shared") { Poller().also { pollers += it } }
        val owners = List(512) { readiness.register(it) }
        assertEquals(1, pollers.size)
        assertEquals(1, Thread.getAllStackTraces().keys.count { it.name == "readiness-test-shared" })
        owners.dropLast(1).forEach { it.close() }
        assertEquals(0, pollers.single().closed.get())
        owners.last().close()
        assertEquals(1, pollers.single().closed.get())
        assertFalse(Thread.getAllStackTraces().keys.any { it.name == "readiness-test-shared" })
        readiness.register(0).close()
        assertEquals(2, pollers.size)
        assertEquals(1, pollers.last().closed.get())
    }

    @Test fun readAndWriteCancellationRemoveOnlyTheirOwnWaiters() = runBlocking { supervisorScope {
        val poller = Poller()
        val readiness = SocketReadiness("readiness-test-cancel") { poller }
        val owner = readiness.register(1)
        val reader = async(start = CoroutineStart.UNDISPATCHED) { owner.await(READABLE) }
        val writer = async(start = CoroutineStart.UNDISPATCHED) { owner.await(WRITABLE) }
        reader.cancelAndJoin()
        assertFalse(writer.isCompleted)
        owner.close()
        assertFailsWith<IOException> { writer.await() }
        assertEquals(1, poller.closed.get())
    } }

    @Test fun unconfinedApplicationContinuationNeverRunsOnReadinessWorker() = runBlocking {
        val entered = CountDownLatch(1)
        val proceed = Semaphore(0)
        val poller = object : SocketPoller<Int> {
            override fun wakeup() { proceed.release() }
            override fun select(interests: List<SocketInterest<Int>>): IntArray {
                if (interests.isNotEmpty()) { entered.countDown(); return IntArray(interests.size) { READABLE } }
                check(proceed.tryAcquire(5, TimeUnit.SECONDS))
                return IntArray(0)
            }
            override fun close() = Unit
        }
        val readiness = SocketReadiness("readiness-test-unconfined") { poller }
        val owner = readiness.register(1)
        val reader = async(Dispatchers.Unconfined, start = CoroutineStart.UNDISPATCHED) {
            owner.await(READABLE)
            Thread.currentThread().name
        }
        try {
            val name = withTimeout(5_000) { reader.await() }
            assertEquals(0, entered.count)
            assertFalse(name == "readiness-test-unconfined")
        } finally { owner.close(); reader.cancelAndJoin() }
    }

    @Test fun lateSnapshotCannotResumeAReplacementWaiter() = runBlocking {
        val selected = CompletableDeferred<Unit>()
        val oldReady = Semaphore(0)
        val nextReady = Semaphore(0)
        val wake = Semaphore(0)
        val polls = AtomicInteger()
        val poller = object : SocketPoller<Int> {
            override fun wakeup() { wake.release() }
            override fun select(interests: List<SocketInterest<Int>>): IntArray {
                if (interests.isEmpty()) {
                    check(wake.tryAcquire(5, TimeUnit.SECONDS)); return IntArray(0)
                }
                if (polls.incrementAndGet() == 1) {
                    selected.complete(Unit)
                    check(oldReady.tryAcquire(5, TimeUnit.SECONDS))
                } else check(nextReady.tryAcquire(5, TimeUnit.SECONDS))
                return IntArray(interests.size) { READABLE }
            }
            override fun close() = Unit
        }
        val owner = SocketReadiness("readiness-test-stale") { poller }.register(1)
        val first = async(start = CoroutineStart.UNDISPATCHED) { owner.await(READABLE) }
        try {
            withTimeout(5_000) { selected.await() }
            first.cancelAndJoin()
            val second = async(start = CoroutineStart.UNDISPATCHED) { owner.await(READABLE) }
            oldReady.release()
            // The new waiter is still held by its own readiness semaphore. It cannot consume an old event.
            withTimeout(5_000) { while (polls.get() < 2) kotlinx.coroutines.yield() }
            assertFalse(second.isCompleted)
            nextReady.release()
            withTimeout(5_000) { second.await() }
        } finally {
            oldReady.release()
            nextReady.release()
            owner.close()
            first.cancelAndJoin()
        }
    }

    @Test fun uncertainBackendRetirementCannotBeReclassifiedByAnIdempotentCloseOrNewOwner() {
        val poller = Poller().apply { closeFailure = true }
        val readiness = SocketReadiness("readiness-test-quarantine") { poller }
        val owner = readiness.register(1)
        repeat(2) { attempt ->
            assertFailsWith<IOException>("retirement attempt $attempt; closed=${poller.closed.get()}") { owner.close() }
        }
        assertFailsWith<IOException> { readiness.register(2) }
        assertEquals(1, poller.closed.get(), "Uncertain backend close must not be repeated")
    }

    @Test fun failedThreadStartClosesOriginalBackendOnceAndCannotCreateAnUnobservedReplacement() {
        val poller = Poller().apply { closeFailure = true }
        val creations = AtomicInteger()
        val readiness = SocketReadiness("readiness-test-start-failure", startThread = {
            throw IOException("injected thread start failure")
        }) { creations.incrementAndGet(); poller }
        val failure = assertFailsWith<IOException> { readiness.register(1) }
        assertEquals("injected thread start failure", failure.cause?.message)
        assertEquals("test retirement", failure.cause?.suppressedExceptions?.single()?.message)
        assertFailsWith<IOException> { readiness.register(2) }
        assertEquals(1, creations.get())
        assertEquals(1, poller.closed.get())
        assertFalse(Thread.getAllStackTraces().keys.any { it.name == "readiness-test-start-failure" })
    }

    @Test fun actualSelectFailureFailsBothWaitersAndRetiresOriginalPoller() = runBlocking { supervisorScope {
        val poller = Poller().apply { selectFailure = true }
        val readiness = SocketReadiness("readiness-test-select-failure") { poller }
        val owner = readiness.register(1)
        try {
            val read = async(start = CoroutineStart.UNDISPATCHED) { owner.await(READABLE) }
            val write = async(start = CoroutineStart.UNDISPATCHED) { owner.await(WRITABLE) }
            withTimeout(5_000) {
                assertFailsWith<IOException> { read.await() }
                assertFailsWith<IOException> { write.await() }
            }
            assertFailsWith<IOException> { readiness.register(2) }
        } finally { owner.close() }
        assertEquals(1, poller.closed.get())
    } }
}
