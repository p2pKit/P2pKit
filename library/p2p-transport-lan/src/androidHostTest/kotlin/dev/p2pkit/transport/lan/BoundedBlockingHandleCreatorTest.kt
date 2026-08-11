package dev.p2pkit.transport.lan

import java.io.IOException
import java.io.InterruptedIOException
import java.net.SocketTimeoutException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicReference
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Android-source-set ownership tests for bounded blocking JmDNS construction. */
class BoundedBlockingHandleCreatorTest {
    private class FakeHandle

    @Test
    fun completedConstructionReturnsExactHandleAndFailureAllowsRetry() {
        val creator = creator()
        val expected = FakeHandle()
        assertSame(expected, creator.create { expected })

        val failure = IOException("injected factory failure")
        assertSame(failure, assertFailsWith<IOException> { creator.create { throw failure } })
        creator.create { FakeHandle() }
    }

    @Test
    fun timeoutRejectsParallelRetryAndClosesLateOrphanBeforeRecovery() {
        val release = CountDownLatch(1)
        val orphanClosed = CountDownLatch(1)
        val entered = CountDownLatch(1)
        val attempts = AtomicInteger(0)
        val creator = creator(
            closeOrphan = { orphanClosed.countDown() },
            awaitCompletion = forceFirstTimeoutAfter(entered)
        )

        assertFailsWith<SocketTimeoutException> {
            creator.create {
                attempts.incrementAndGet()
                entered.countDown()
                awaitIgnoringInterrupt(release)
                FakeHandle()
            }
        }
        val blocked = assertFailsWith<IOException> { creator.create { FakeHandle() } }
        assertTrue("previous attempt" in blocked.message.orEmpty())
        assertEquals(1, attempts.get())

        release.countDown()
        assertTrue(orphanClosed.await(1, TimeUnit.SECONDS))
        creator.create { FakeHandle() }
    }

    @Test
    fun failedOrphanCleanupPoisonsCreator() {
        val release = CountDownLatch(1)
        val cleanupFailed = CountDownLatch(1)
        val entered = CountDownLatch(1)
        val creator = creator(
            closeOrphan = { throw IOException("injected close failure") },
            onCleanupFailure = { cleanupFailed.countDown() },
            awaitCompletion = forceFirstTimeoutAfter(entered)
        )

        assertFailsWith<SocketTimeoutException> {
            creator.create {
                entered.countDown()
                awaitIgnoringInterrupt(release)
                FakeHandle()
            }
        }
        release.countDown()
        assertTrue(cleanupFailed.await(1, TimeUnit.SECONDS))
        assertTrue(
            "Poisoned" in assertFailsWith<IOException> {
                creator.create { FakeHandle() }
            }.message.orEmpty()
        )
    }

    @Test
    fun interruptedWaiterReturnsBeforeCompletedOrphanCleanupFinishes() {
        val cleanupEntered = CountDownLatch(1)
        val releaseCleanup = CountDownLatch(1)
        val cleanupFinished = CountDownLatch(1)
        val callerReturned = CountDownLatch(1)
        val callerFailure = AtomicReference<Throwable?>()
        val awaitCalls = AtomicInteger()
        val creator = creator(
            closeOrphan = {
                cleanupEntered.countDown()
                awaitIgnoringInterrupt(releaseCleanup)
                cleanupFinished.countDown()
            },
            awaitCompletion = { completion, timeout ->
                if (awaitCalls.getAndIncrement() == 0) {
                    assertTrue(completion.await(1, TimeUnit.SECONDS))
                    throw InterruptedException("injected waiter interruption")
                }
                completion.await(timeout, TimeUnit.MILLISECONDS)
            }
        )

        val caller = Thread {
            callerFailure.set(runCatching { creator.create { FakeHandle() } }.exceptionOrNull())
            callerReturned.countDown()
        }
        caller.start()

        assertTrue(cleanupEntered.await(1, TimeUnit.SECONDS), "orphan cleanup did not start")
        assertTrue(
            callerReturned.await(1, TimeUnit.SECONDS),
            "an interrupted caller must not synchronously own a blocking orphan close"
        )
        assertIs<InterruptedIOException>(callerFailure.get())
        assertTrue(
            "Cleaning" in assertFailsWith<IOException> {
                creator.create { FakeHandle() }
            }.message.orEmpty()
        )

        releaseCleanup.countDown()
        assertTrue(cleanupFinished.await(1, TimeUnit.SECONDS))
        caller.join(1_000)
        creator.create { FakeHandle() }
    }

    private fun creator(
        closeOrphan: (FakeHandle) -> Unit = {},
        onCleanupFailure: (Throwable) -> Unit = {},
        awaitCompletion: (CountDownLatch, Long) -> Boolean = { completion, timeout ->
            completion.await(timeout, TimeUnit.MILLISECONDS)
        }
    ): BoundedBlockingHandleCreator<FakeHandle> =
        BoundedBlockingHandleCreator(
            timeoutMillis = 100,
            threadName = "android-bounded-creator-test",
            closeOrphan = closeOrphan,
            onCleanupFailure = onCleanupFailure,
            awaitCompletion = awaitCompletion
        )

    private fun forceFirstTimeoutAfter(
        entered: CountDownLatch
    ): (CountDownLatch, Long) -> Boolean {
        val awaits = AtomicInteger(0)
        return { completion, timeout ->
            if (awaits.getAndIncrement() == 0) {
                assertTrue(entered.await(1, TimeUnit.SECONDS), "factory worker did not start")
                false
            } else {
                completion.await(timeout, TimeUnit.MILLISECONDS)
            }
        }
    }

    private fun awaitIgnoringInterrupt(latch: CountDownLatch) {
        while (true) {
            try {
                latch.await()
                return
            } catch (_: InterruptedException) {
                // Reproduce a third-party constructor that ignores interruption.
            }
        }
    }
}
