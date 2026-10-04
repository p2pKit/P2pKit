package dev.p2pkit.sample.rpc.lab

import java.io.IOException
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.PosixFilePermissions
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class LabCleanupOwnerTest {
    @Test
    fun successfulCleanupPublishesOnlyAfterEveryResourceAndNeverRepeats() {
        val events = mutableListOf<String>()
        val owner = LabCleanupOwner(listOf(1, 2), { events += "retire-$it" }, { events += "closed" })
        owner.close()
        owner.close()
        assertEquals(listOf("retire-1", "retire-2", "closed"), events)
    }

    @Test
    fun failedVaultRetainsItsFailureAndForeignFileButDoesNotStrandIndependentVaults() = fixture { root ->
        val directories = listOf("first", "failed", "last").map { LabFiles.newDirectory(root, it) }
        val vaults = directories.map { LabVault(it) }
        vaults.forEach { it.putIfAbsent("key", byteArrayOf(1)) }
        val replaced = directories[1].resolve(LabFiles.sha256("key".toByteArray()) + ".aesgcm")
        LabFiles.write(replaced, byteArrayOf(2), replace = true)
        val receipt = root.resolve("clients-closed.txt")
        val owner = LabCleanupOwner(vaults, LabVault::destroy) {
            LabFiles.write(receipt, "closed=true\nfixturesRemoved=true\n".toByteArray())
        }
        val failure = assertFails { owner.close() }
        assertFalse(Files.exists(directories[0]))
        assertFalse(Files.exists(directories[2]))
        assertContentEquals(byteArrayOf(2), LabFiles.read(replaced))
        assertFalse(Files.exists(receipt))
        assertSame(failure, assertFails { owner.close() })
        assertContentEquals(byteArrayOf(2), LabFiles.read(replaced))
        assertFalse(Files.exists(receipt))
    }

    @Test
    fun multipleRetirementFailuresRemainOrderedAndTheSameFailureCannotSuppressItself() {
        val first = IOException("synthetic first failure")
        val second = IOException("synthetic second failure")
        val retired = mutableListOf<Int>()
        var published = false
        val owner = LabCleanupOwner(listOf(1, 2, 3), {
            retired += it
            throw if (it == 2) second else first
        }, { published = true })
        assertSame(first, assertFails { owner.close() })
        assertSame(first, assertFails { owner.close() })
        assertEquals(listOf(second), first.suppressed.toList())
        assertEquals(listOf(1, 2, 3), retired)
        assertFalse(published)
    }

    @Test
    fun failedReceiptCannotBecomeSuccessfulCloseOrRepeatNonIdempotentRetirement() {
        val failure = IOException("synthetic receipt publication failed")
        var retired = 0
        var publications = 0
        val owner = LabCleanupOwner(listOf(Unit), { retired++ }, {
            publications++
            throw failure
        })
        assertSame(failure, assertFails { owner.close() })
        assertSame(failure, assertFails { owner.close() })
        assertEquals(1, retired)
        assertEquals(1, publications)
    }

    @Test
    fun concurrentCloseWaitsForTheSuccessfulPhysicalAttempt() = concurrentClose(null)

    @Test
    fun concurrentCloseWaitsAndReceivesTheExactPhysicalFailure() =
        concurrentClose(IOException("synthetic concurrent cleanup failed"))

    @Test
    fun reentrantCleanupFailsAndThatExactFailureRemainsTerminal() {
        lateinit var owner: LabCleanupOwner<Unit>
        var published = false
        owner = LabCleanupOwner(listOf(Unit), { owner.close() }, { published = true })
        val failure = assertFails { owner.close() }
        assertSame(failure, assertFails { owner.close() })
        assertFalse(published)
    }

    private fun concurrentClose(failure: IOException?) {
        val physicalEntered = CountDownLatch(1)
        val releasePhysical = CountDownLatch(1)
        val secondStarted = CountDownLatch(1)
        val secondThread = AtomicReference<Thread>()
        var retirements = 0
        var publications = 0
        val owner = LabCleanupOwner(listOf(Unit), {
            retirements++
            physicalEntered.countDown()
            check(releasePhysical.await(5, TimeUnit.SECONDS)) { "Synthetic physical cleanup was not released" }
            if (failure != null) throw failure
        }, { publications++ })
        val executor = Executors.newFixedThreadPool(2)
        try {
            val first = executor.submit<Throwable?> { runCatching { owner.close() }.exceptionOrNull() }
            assertTrue(physicalEntered.await(5, TimeUnit.SECONDS))
            val second = executor.submit<Throwable?> {
                secondThread.set(Thread.currentThread())
                secondStarted.countDown()
                runCatching { owner.close() }.exceptionOrNull()
            }
            assertTrue(secondStarted.await(5, TimeUnit.SECONDS))
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            while (secondThread.get().state != Thread.State.BLOCKED && !second.isDone &&
                System.nanoTime() < deadline) Thread.yield()
            // The second caller must actually contend on the owner's monitor, not merely be unscheduled.
            assertEquals(Thread.State.BLOCKED, secondThread.get().state)
            assertFalse(second.isDone)
            releasePhysical.countDown()
            assertSame(failure, first.get(5, TimeUnit.SECONDS))
            assertSame(failure, second.get(5, TimeUnit.SECONDS))
            assertSame(failure, runCatching { owner.close() }.exceptionOrNull())
        } finally {
            releasePhysical.countDown()
            executor.shutdown()
            assertTrue(executor.awaitTermination(5, TimeUnit.SECONDS))
        }
        assertEquals(1, retirements)
        assertEquals(if (failure == null) 1 else 0, publications)
    }

    private fun fixture(block: (Path) -> Unit) {
        val root = Files.createTempDirectory("rpc-lab-cleanup-", PosixFilePermissions.asFileAttribute(
            PosixFilePermissions.fromString("rwx------"),
        )).toRealPath()
        try {
            block(root)
        } finally {
            Files.walk(root).use { paths -> paths.sorted(Comparator.reverseOrder()).forEach(Files::delete) }
        }
    }
}
