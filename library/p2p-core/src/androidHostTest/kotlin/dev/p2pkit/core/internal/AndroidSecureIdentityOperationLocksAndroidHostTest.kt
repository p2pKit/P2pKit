package dev.p2pkit.core.internal

import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.P2pError
import java.io.Closeable
import java.io.File
import java.io.IOException
import java.io.RandomAccessFile
import java.nio.channels.OverlappingFileLockException
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.CancellationException

/** Exercises the production process/file-lock path without Context or Keystore stubs. */
class AndroidSecureIdentityOperationLocksAndroidHostTest {
    @Test
    fun heldNamespaceDoesNotBlockAnotherNamespaceAndFileLockStillOwnsTheOperation() {
        val baseline = AndroidSecureIdentityOperationLocks.entryCountForTest()
        LockFixture().use { fixture ->
            val entered = CountDownLatch(1)
            val release = CountDownLatch(1)
            try {
                val owner = fixture.workers.submit<String> {
                    withAndroidIdentityStorageLock("android-lock-a", File(fixture.root, "a")) {
                        entered.countDown()
                        await(release)
                        "a"
                    }
                }
                await(entered)
                val independentDirectory = File(fixture.root, "b")
                val independent = fixture.workers.submit<String> {
                    withAndroidIdentityStorageLock("android-lock-b", independentDirectory) {
                        RandomAccessFile(File(independentDirectory, "identity.lock"), "rw").use { file ->
                            assertFailsWith<OverlappingFileLockException> { file.channel.tryLock() }
                        }
                        "b"
                    }
                }

                assertEquals("b", independent.get(5, TimeUnit.SECONDS))
                assertFalse(owner.isDone, "unrelated I/O must finish while A still owns its lock")
                RandomAccessFile(File(independentDirectory, "identity.lock"), "rw").use { file ->
                    assertNotNull(file.channel.tryLock()).use { }
                }
                release.countDown()
                assertEquals("a", owner.get(5, TimeUnit.SECONDS))
            } finally {
                release.countDown()
            }
        }
        assertEquals(baseline, AndroidSecureIdentityOperationLocks.entryCountForTest())
    }

    @Test
    fun sameNamespaceAcrossRootsKeepsQueuedEntryUntilLastCallerAndOneDurableWinner() {
        val baseline = AndroidSecureIdentityOperationLocks.entryCountForTest()
        val key = "android-shared-keystore-alias"
        LockFixture().use { fixture ->
            val firstEntered = CountDownLatch(1)
            val releaseFirst = CountDownLatch(1)
            val secondEntered = CountDownLatch(1)
            val releaseSecond = CountDownLatch(1)
            val active = AtomicInteger()
            // Different filesystem roots still address the same Keystore alias.
            // This synthetic record models that one shared durable winner.
            val record = File(fixture.root, "shared-alias-record")
            fun operation(root: String, entered: CountDownLatch?, release: CountDownLatch?): String =
                withAndroidIdentityStorageLock(key, File(fixture.root, root)) {
                    val owners = active.incrementAndGet()
                    try {
                        assertEquals(1, owners, "same-alias operations overlapped")
                        if (!record.exists()) record.writeText(root)
                        entered?.countDown()
                        release?.let(::await)
                        record.readText()
                    } finally {
                        active.decrementAndGet()
                    }
                }

            try {
                val first = fixture.workers.submit<String> { operation("first", firstEntered, releaseFirst) }
                await(firstEntered)
                val second = fixture.workers.submit<String> { operation("second", secondEntered, releaseSecond) }
                awaitUsers(key, 2)
                assertFalse(second.isDone)

                releaseFirst.countDown()
                assertEquals("first", first.get(5, TimeUnit.SECONDS))
                await(secondEntered)
                val late = fixture.workers.submit<String> { operation("late", null, null) }
                awaitUsers(key, 2)

                assertEquals(baseline + 1, AndroidSecureIdentityOperationLocks.entryCountForTest())
                assertFalse(late.isDone, "a late caller must not replace an entry still owned by the queued caller")
                releaseSecond.countDown()
                assertEquals("first", second.get(5, TimeUnit.SECONDS))
                assertEquals("first", late.get(5, TimeUnit.SECONDS))
                assertEquals("first", record.readText())
                assertEquals(0, active.get())
            } finally {
                releaseFirst.countDown()
                releaseSecond.countDown()
            }
        }
        assertEquals(baseline, AndroidSecureIdentityOperationLocks.entryCountForTest())
    }

    @Test
    fun failuresAndTransientNamespacesReleaseOperationEntriesAndFileLocks() {
        val baseline = AndroidSecureIdentityOperationLocks.entryCountForTest()
        LockFixture().use { fixture ->
            val directory = File(fixture.root, "failure")
            val failure = IOException("injected identity operation failure")
            val error = assertFailsWith<P2pError.LocalIdentityUnavailable> {
                withAndroidIdentityStorageLock("android-failed-operation", directory) { throw failure }
            }
            assertEquals(LocalIdentityFailureKind.PERSISTENCE_FAILED, error.kind)
            assertSame(failure, error.cause)
            val cancellation = CancellationException("cancel identity operation")
            assertSame(
                cancellation,
                assertFailsWith<CancellationException> {
                    withAndroidIdentityStorageLock("android-failed-operation", directory) { throw cancellation }
                }
            )
            assertEquals(baseline, AndroidSecureIdentityOperationLocks.entryCountForTest())
            RandomAccessFile(File(directory, "identity.lock"), "rw").use { file ->
                assertNotNull(file.channel.tryLock()).use { }
            }

            repeat(32) { index ->
                withAndroidIdentityStorageLock("android-transient-$index", File(fixture.root, "transient-$index")) {
                    assertEquals(baseline + 1, AndroidSecureIdentityOperationLocks.entryCountForTest())
                }
            }
        }
        assertEquals(baseline, AndroidSecureIdentityOperationLocks.entryCountForTest())
    }

    private class LockFixture : Closeable {
        val root: File = Files.createTempDirectory("p2pkit-identity-locks-").toFile()
        val workers = Executors.newFixedThreadPool(3)

        override fun close() {
            workers.shutdownNow()
            check(workers.awaitTermination(5, TimeUnit.SECONDS)) { "identity operation workers did not stop" }
            check(root.deleteRecursively()) { "identity operation test directory cleanup failed" }
        }
    }

    private fun awaitUsers(key: String, count: Int) {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
        while (AndroidSecureIdentityOperationLocks.usersForTest(key) != count) {
            check(System.nanoTime() < deadline) { "identity caller did not retain the queued operation entry" }
            Thread.yield()
        }
    }

    private fun await(gate: CountDownLatch) {
        assertTrue(gate.await(5, TimeUnit.SECONDS), "identity operation did not reach its barrier")
    }
}
